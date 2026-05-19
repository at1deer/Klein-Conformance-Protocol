use std::path::PathBuf;

use clap::{Parser, Subcommand};
use klein_verifier_rs::bundle::{verify_bundle, verify_bundle_result};
use klein_verifier_rs::fixtures::verify_fixtures;

#[derive(Parser)]
#[command(name = "klein-verifier-rs")]
#[command(about = "Minimal non-Python verifier slice for Klein protocol fixtures.")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    VerifyFixtures {
        fixture_index: PathBuf,
        #[arg(long)]
        json: bool,
    },
    VerifyBundle {
        bundle: PathBuf,
        #[arg(long)]
        json: bool,
    },
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::VerifyFixtures {
            fixture_index,
            json,
        } => {
            let summary = verify_fixtures(&fixture_index)?;
            if json {
                println!(
                    "{{\"verifier\":\"klein-verifier-rs\",\"result_version\":\"klein.cross_language_verifier_result.v1\",\"passed\":{},\"failed\":{}}}",
                    summary.passed, summary.failed
                );
            } else {
                println!(
                    "Klein Rust verifier: {} fixtures passed, {} failed",
                    summary.passed, summary.failed
                );
                for result in &summary.results {
                    println!(
                        "  {}: {} ({})",
                        result.fixture_id, result.status, result.message
                    );
                }
            }
            if summary.failed > 0 {
                anyhow::bail!("fixture verification failed");
            }
        }
        Command::VerifyBundle { bundle, json } => {
            if json {
                let result = verify_bundle_result(&bundle);
                println!("{}", serde_json::to_string_pretty(&result)?);
                if !result.ok() {
                    anyhow::bail!("bundle verification failed");
                }
            } else {
                let result = verify_bundle(&bundle)?;
                println!(
                    "Klein Rust bundle verifier: pass trusted_key_ids={}",
                    result.trusted_key_ids.join(",")
                );
            }
        }
    }
    Ok(())
}
