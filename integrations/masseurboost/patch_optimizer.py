#!/usr/bin/env python3
"""Patch the mirrored C++ optimizer with a public, receipt-backed trial endpoint."""
from __future__ import annotations

import argparse
from pathlib import Path

PUBLIC_MUTATION_OLD = 'if (m == "POST" && p != "/api/metrics/ingest") return true;'
PUBLIC_MUTATION_NEW = 'if (m == "POST" && p != "/api/metrics/ingest" && p != "/api/trials") return true;'
ANCHOR = '    } else if (path == "/api/metrics/ingest" && method == "POST") {'

TRIAL_ROUTES = r'''    } else if (path == "/api/trials" && method == "GET") {
        std::string trials = read_file(CONTENT_DIR + "/trials.jsonl");
        int trial_count = 0;
        if (!trials.empty()) {
            for (char c : trials) if (c == '\n') trial_count++;
            if (trials.back() != '\n') trial_count++;
        }
        response = "{\"status\":\"ok\",\"trial_count\":" + std::to_string(trial_count) +
                   ",\"storage\":\"content/trials.jsonl\",\"activation\":\"manual_review_required\"}";
    } else if (path == "/api/trials" && method == "POST") {
        if (body.empty() || body.size() > 12000 || body.front() != '{') {
            code = 400;
            response = "{\"status\":\"rejected\",\"reason\":\"invalid or oversized JSON payload\"}";
        } else {
            std::string lower_body = body;
            for (char& c : lower_body) c = (char)tolower(c);
            const char* forbidden_keys[] = {
                "\"cookie\"", "\"cookies\"", "\"token\"", "\"access_token\"",
                "\"refresh_token\"", "\"authorization\"", "\"password\"", "\"bearer\"", nullptr
            };
            bool has_secret = false;
            std::string forbidden_key;
            for (int i = 0; forbidden_keys[i]; i++) {
                if (lower_body.find(forbidden_keys[i]) != std::string::npos) {
                    has_secret = true;
                    forbidden_key = forbidden_keys[i];
                    break;
                }
            }
            const bool has_required_fields =
                body.find("\"name\"") != std::string::npos &&
                body.find("\"contact\"") != std::string::npos &&
                body.find("\"profile_url\"") != std::string::npos &&
                body.find("\"plan\"") != std::string::npos &&
                body.find("\"consent\":true") != std::string::npos;
            if (has_secret) {
                code = 400;
                std::string receipt = write_receipt(
                    "trial_signup_rejected", "rejected", 0, "payload contains a secret-bearing key",
                    "\"rejected_key\": \"" + json_escape(forbidden_key) + "\""
                );
                response = "{\"status\":\"rejected\",\"reason\":\"Do not submit passwords, cookies, tokens, or authorization data\",\"receipt\":\"" + json_escape(receipt) + "\"}";
            } else if (!has_required_fields) {
                code = 400;
                response = "{\"status\":\"rejected\",\"reason\":\"name, contact, profile_url, plan, and consent are required\"}";
            } else {
                const std::string trial_id = "TRIAL-" + compact_timestamp();
                const std::string trial_path = CONTENT_DIR + "/trials.jsonl";
                std::ofstream f(trial_path, std::ios::app);
                if (!f) {
                    code = 500;
                    response = "{\"status\":\"failed\",\"reason\":\"could not write trial ledger\"}";
                } else {
                    f << "{\"received_at\":\"" << iso_timestamp() << "\",\"trial_id\":\""
                      << json_escape(trial_id) << "\",\"payload\":" << body << "}\n";
                    f.close();
                    const std::string receipt = write_receipt(
                        "trial_signup", "success", 0, "trial signup accepted",
                        "\"trial_id\": \"" + json_escape(trial_id) + "\", \"output_file\": \"" + json_escape(trial_path) + "\""
                    );
                    response = "{\"status\":\"accepted\",\"trial_id\":\"" + json_escape(trial_id) +
                               "\",\"trial_days\":7,\"activation\":\"manual_review_required\",\"receipt\":\"" +
                               json_escape(receipt) + "\"}";
                }
            }
        }
'''


def patch(path: Path) -> None:
    source = path.read_text()
    if PUBLIC_MUTATION_NEW not in source:
        if PUBLIC_MUTATION_OLD not in source:
            raise SystemExit("Could not find is_mutation allowlist anchor")
        source = source.replace(PUBLIC_MUTATION_OLD, PUBLIC_MUTATION_NEW, 1)
    if 'path == "/api/trials" && method == "POST"' not in source:
        if ANCHOR not in source:
            raise SystemExit("Could not find metrics ingestion route anchor")
        source = source.replace(ANCHOR, TRIAL_ROUTES + ANCHOR, 1)
    path.write_text(source)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    patch(args.path)
    print(f"patched {args.path}")


if __name__ == "__main__":
    main()
