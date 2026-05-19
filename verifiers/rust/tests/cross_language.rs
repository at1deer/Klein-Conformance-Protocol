use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use klein_verifier_rs::bundle::{verify_bundle, verify_bundle_result};
use klein_verifier_rs::fixtures::verify_fixtures;
use zip::write::SimpleFileOptions;

#[test]
fn cross_language_fixture_index_passes() {
    let summary = verify_fixtures(Path::new(
        "../../tests/fixtures/cross_language/fixtures.json",
    ))
    .unwrap();
    assert_eq!(summary.failed, 0, "{summary:#?}");
    assert!(summary.passed >= 6);
}

#[test]
fn valid_bundle_verifies() {
    let result = verify_bundle(Path::new(
        "../../tests/fixtures/run_bundle/valid_signed_run.kcprun",
    ))
    .unwrap();
    assert_eq!(result.trusted_key_ids, vec!["klein-test-backend-001"]);
}

#[test]
fn path_traversal_bundle_is_rejected() {
    let error = verify_bundle(Path::new(
        "../../tests/fixtures/run_bundle/path_traversal_attack.kcprun",
    ))
    .unwrap_err()
    .to_string();
    assert!(error.contains("RUN_BUNDLE_PATH_TRAVERSAL"), "{error}");
}

#[test]
fn absolute_path_bundle_member_is_rejected() {
    let bundle = malicious_bundle("absolute", |writer, options, entries| {
        copy_entries(writer, options, entries, None);
        writer.start_file("/absolute.txt", options).unwrap();
        std::io::Write::write_all(writer, b"bad").unwrap();
    });
    assert_error(&bundle, "RUN_BUNDLE_PATH_TRAVERSAL", "bundle_schema");
}

#[test]
fn duplicate_bundle_member_is_rejected() {
    assert_error(
        Path::new("../../tests/fixtures/run_bundle/duplicate_member.kcprun"),
        "RUN_BUNDLE_INVALID",
        "bundle_schema",
    );
}

#[test]
fn missing_declared_bundle_entry_is_rejected() {
    let bundle = malicious_bundle("missing", |writer, options, entries| {
        copy_entries(writer, options, entries, Some("trust/trust_policy.json"));
    });
    assert_error(&bundle, "RUN_BUNDLE_MISSING_ENTRY", "bundle_entry_hashes");
}

#[test]
fn undeclared_bundle_file_is_rejected() {
    let bundle = malicious_bundle("undeclared", |writer, options, entries| {
        copy_entries(writer, options, entries, None);
        writer.start_file("extra/undeclared.txt", options).unwrap();
        std::io::Write::write_all(writer, b"bad").unwrap();
    });
    assert_error(&bundle, "RUN_BUNDLE_INVALID", "bundle_schema");
}

#[test]
fn bundle_entry_hash_mismatch_is_rejected() {
    assert_error(
        Path::new("../../tests/fixtures/run_bundle/bundle_hash_mismatch.kcprun"),
        "RUN_BUNDLE_HASH_MISMATCH",
        "bundle_entry_hashes",
    );
}

#[test]
fn unsupported_bundle_format_is_rejected() {
    let path = temp_path("unsupported", "txt");
    std::fs::write(&path, b"not a bundle").unwrap();
    assert_error(&path, "RUN_BUNDLE_UNSUPPORTED_FORMAT", "bundle_schema");
}

fn assert_error(path: &Path, error_code: &str, check: &str) {
    let result = verify_bundle_result(path);
    assert_eq!(result.overall_status, "fail", "{result:#?}");
    let error = result.errors.first().expect("expected verifier error");
    assert_eq!(error.error_code, error_code, "{result:#?}");
    assert_eq!(error.check, check, "{result:#?}");
}

fn malicious_bundle(
    label: &str,
    write_entries: impl FnOnce(
        &mut zip::ZipWriter<std::fs::File>,
        SimpleFileOptions,
        &[(String, Vec<u8>)],
    ),
) -> std::path::PathBuf {
    let source = Path::new("../../tests/fixtures/run_bundle/valid_signed_run.kcprun");
    let mut archive = zip::ZipArchive::new(std::fs::File::open(source).unwrap()).unwrap();
    let mut entries = Vec::new();
    for index in 0..archive.len() {
        let mut file = archive.by_index(index).unwrap();
        if file.is_dir() {
            continue;
        }
        let mut data = Vec::new();
        std::io::Read::read_to_end(&mut file, &mut data).unwrap();
        entries.push((file.name().to_string(), data));
    }

    let path = temp_path(label, "kcprun");
    let file = std::fs::File::create(&path).unwrap();
    let mut writer = zip::ZipWriter::new(file);
    let options = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);
    write_entries(&mut writer, options, &entries);
    writer.finish().unwrap();
    path
}

fn copy_entries(
    writer: &mut zip::ZipWriter<std::fs::File>,
    options: SimpleFileOptions,
    entries: &[(String, Vec<u8>)],
    omit: Option<&str>,
) {
    for (name, data) in entries {
        if Some(name.as_str()) == omit {
            continue;
        }
        writer.start_file(name, options).unwrap();
        std::io::Write::write_all(writer, data).unwrap();
    }
}

fn temp_path(label: &str, extension: &str) -> std::path::PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "klein-rust-verifier-{label}-{}-{nanos}.{extension}",
        std::process::id()
    ))
}
