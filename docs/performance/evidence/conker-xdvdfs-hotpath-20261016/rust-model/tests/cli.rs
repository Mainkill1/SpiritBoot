// SPDX-License-Identifier: GPL-2.0-or-later
use std::fs;
use std::process::Command;

fn temp_file(label: &str) -> std::path::PathBuf {
    std::env::temp_dir().join(format!(
        "optical-forwarding-{label}-{}-{}.tsv",
        std::process::id(),
        std::thread::current().name().unwrap_or("test")
    ))
}

#[test]
fn analyzer_reports_conservative_operation_counts() {
    let input = temp_file("valid");
    fs::write(
        &input,
        concat!(
            "file\t0\t4096\t8192\t32\t0\t0\t0\t4096\t3\t1\t1\t0\t1\t1\t4096\n",
            "metadata\t0\t2048\t2048\t64\t0\t0\t0\t8192\t3\t1\t0\t0\t0\t0\t0\n",
        ),
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_analyze-trace"))
        .arg(&input)
        .output()
        .unwrap();
    let _ = fs::remove_file(&input);
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8(output.stdout).unwrap();
    for expected in [
        "\"samples\":2",
        "\"forwarded\":1",
        "\"existing\":1",
        "\"removed_child_requests\":1",
        "\"Metadata\":1",
    ] {
        assert!(stdout.contains(expected), "missing {expected}: {stdout}");
    }
}

#[test]
fn analyzer_fails_closed_on_a_malformed_record() {
    let input = temp_file("invalid");
    fs::write(&input, "file\tmissing\n").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_analyze-trace"))
        .arg(&input)
        .output()
        .unwrap();
    let _ = fs::remove_file(&input);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("line 1"));
}
