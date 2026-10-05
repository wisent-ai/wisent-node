//! `wisent-node-release`: the release contract of the `wisent` npm package.
//!
//! - `surface [--root DIR] [--tolerant]` prints `{"surface": [...]}` for the distribution at DIR;
//! - `baseline [--root DIR] [--output FILE | --stdout] [--tolerant]` writes `released-surface.json`
//!   from the best tier reachable now, or prints it without touching the committed file;
//! - `baseline --probe NAME` asks npm about NAME through the subject's own code path;
//! - `baseline --marker-claims MARKER` prints whether MARKER's tier claims a registry.
//!
//! Exit 1 is a refusal with its reason on standard error.

mod baseline;
mod surface;

use std::path::PathBuf;
use std::process::ExitCode;

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "wisent-node-release", about = "The release contract of the wisent npm package")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Print the public surface of the distribution.
    Surface {
        /// Directory holding package.json.
        #[arg(long, default_value = ".")]
        root: PathBuf,
        /// Skip unreadable non-entry modules and name them; for an already-published artifact only.
        #[arg(long)]
        tolerant: bool,
    },
    /// Recover the surface of the version actually published.
    Baseline {
        /// Directory holding package.json.
        #[arg(long, default_value = ".")]
        root: PathBuf,
        /// Where to write the baseline.
        #[arg(long, default_value = "released-surface.json", conflicts_with = "stdout")]
        output: PathBuf,
        /// Print the baseline instead of writing it.
        #[arg(long)]
        stdout: bool,
        /// Pass tolerant reading to the surface reader.
        #[arg(long)]
        tolerant: bool,
        /// Ask npm about NAME and print published, absent or unproven.
        #[arg(long, value_name = "NAME", conflicts_with = "marker_claims")]
        probe: Option<String>,
        /// Print whether MARKER's tier claims a registry.
        #[arg(long, value_name = "MARKER")]
        marker_claims: Option<String>,
    },
}

fn baseline(root: PathBuf, output: PathBuf, stdout: bool, tolerant: bool) -> Result<(), String> {
    let root = root.canonicalize().map_err(|error| format!("{}: {error}", root.display()))?;
    let scratch = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target").join("baseline-artifact");
    let document = baseline::build(&root, tolerant, &scratch)?;
    let text = serde_json::to_string_pretty(&document).map_err(|error| error.to_string())? + "\n";
    if stdout {
        print!("{text}");
        return Ok(());
    }
    std::fs::write(&output, &text).map_err(|error| format!("{}: {error}", output.display()))?;
    let marker = document["source"].as_str().unwrap_or_default().split(' ').next().unwrap_or_default();
    eprintln!("wrote {}: {marker}", output.display());
    Ok(())
}

fn main() -> ExitCode {
    let outcome = match Cli::parse().command {
        Command::Surface { root, tolerant } => root
            .canonicalize()
            .map_err(|error| format!("{}: {error}", root.display()))
            .and_then(|root| surface::compute(&root, tolerant))
            .and_then(|names| serde_json::to_string_pretty(&serde_json::json!({ "surface": names })).map_err(|error| error.to_string()))
            .map(|text| println!("{text}")),
        Command::Baseline { marker_claims: Some(marker), .. } => {
            println!("{}", baseline::marker_claim(&marker));
            Ok(())
        }
        Command::Baseline { probe: Some(name), .. } => match baseline::report_probe(&name) {
            Ok(line) => {
                println!("{line}");
                Ok(())
            }
            // The answer goes to standard output either way, so a caller reads
            // why the lookup is unproven, and the exit status says it is not an answer.
            Err(line) => {
                println!("{line}");
                return ExitCode::FAILURE;
            }
        },
        Command::Baseline { root, output, stdout, tolerant, .. } => baseline(root, output, stdout, tolerant),
    };
    match outcome {
        Ok(()) => ExitCode::SUCCESS,
        Err(refusal) => {
            eprintln!("{refusal}");
            ExitCode::FAILURE
        }
    }
}
