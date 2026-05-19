use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::errors::{err, Result};

pub fn canonical_json(value: &Value) -> Result<String> {
    #[allow(deprecated)]
    vr_jcs::to_canon_string(value)
        .map_err(|error| err(format!("JCS_CANONICALIZATION_FAILED: {error}")))
}

pub fn canonical_sha256_ref(value: &Value) -> Result<String> {
    Ok(format!(
        "sha256:{}",
        sha256_hex(canonical_json(value)?.as_bytes())
    ))
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn sha256_ref(bytes: &[u8]) -> String {
    format!("sha256:{}", sha256_hex(bytes))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn canonicalizes_basic_object() {
        assert_eq!(
            canonical_json(&json!({"b": 2, "a": 1})).unwrap(),
            r#"{"a":1,"b":2}"#
        );
    }

    #[test]
    fn canonicalizes_number_fixture() {
        let value: Value = serde_json::from_str(
            r#"{"small":0.000001,"smaller":1e-7,"large":1e21,"intlike":1.0,"fraction":333333333.33333329}"#,
        )
        .unwrap();
        assert_eq!(
            canonical_json(&value).unwrap(),
            r#"{"fraction":333333333.3333333,"intlike":1,"large":1e+21,"small":0.000001,"smaller":1e-7}"#
        );
    }
}
