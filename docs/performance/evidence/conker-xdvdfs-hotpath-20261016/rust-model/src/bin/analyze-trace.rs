// SPDX-License-Identifier: GPL-2.0-or-later
use optical_forwarding_model::{estimate, parse_trace_line};
use std::fmt::Write as _;
use std::fs;
use std::path::PathBuf;

fn run() -> Result<String, String> {
    let mut args = std::env::args_os();
    let _program = args.next();
    let input = PathBuf::from(args.next().ok_or("usage: analyze-trace INPUT.tsv")?);
    if args.next().is_some() {
        return Err("usage: analyze-trace INPUT.tsv".into());
    }
    let bytes = fs::read_to_string(&input)
        .map_err(|error| format!("cannot read {}: {error}", input.display()))?;
    let mut requests = Vec::new();
    for (index, line) in bytes.lines().enumerate() {
        let request = parse_trace_line(line)
            .map_err(|error| format!("line {}: {error:?}", index + 1))?;
        requests.push(request);
    }
    let report = estimate(requests);
    let mut refusals = String::new();
    for (index, (reason, count)) in report.refusals.iter().enumerate() {
        if index != 0 {
            refusals.push(',');
        }
        write!(&mut refusals, "\"{reason:?}\":{count}").expect("writing to String");
    }
    Ok(format!(
        concat!(
            "{{\"samples\":{},\"forwarded\":{},\"existing\":{},",
            "\"complete_zero\":{},\"removed_child_requests\":{},",
            "\"removed_mdl_pairs\":{},\"removed_internal_waits\":{},",
            "\"refusals\":{{{}}}}}"
        ),
        report.samples,
        report.forwarded,
        report.existing,
        report.complete_zero,
        report.removed_child_requests,
        report.removed_mdl_pairs,
        report.removed_internal_waits,
        refusals,
    ))
}

fn main() {
    match run() {
        Ok(report) => println!("{report}"),
        Err(error) => {
            eprintln!("FAIL: {error}");
            std::process::exit(2);
        }
    }
}
