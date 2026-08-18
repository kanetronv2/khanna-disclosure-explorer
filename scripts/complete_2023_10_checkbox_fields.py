#!/usr/bin/env python3
"""Complete scan-encoded checkbox fields in the rebuilt 2023-10 PTR."""

import json
from pathlib import Path


PTR = Path(__file__).resolve().parents[1] / "docs/2023-10/text"


def main():
    transactions = partial_true = cap_true = 0
    for path in sorted(PTR.glob("page-*.json")):
        data = json.loads(path.read_text())
        changed = False
        for row in data.get("rows", []):
            if row.get("kind") != "tx":
                continue
            transactions += 1
            assert isinstance(row.get("cap_gain_over_200"), bool), path
            # The scan rebuild transcribed a checked Partial Transaction box as
            # ``tx_type = Partial Sale``.  Preserve that scan evidence in the
            # dedicated boolean and canonicalize the transaction type to Sale.
            marked_partial = (
                row.get("partial_sale") is True
                or row.get("tx_type") == "Partial Sale"
            )
            if row.get("tx_type") == "Partial Sale":
                row["tx_type"] = "Sale"
                changed = True
            if row.get("partial_sale") is not marked_partial:
                row["partial_sale"] = marked_partial
                changed = True
            cap_true += row["cap_gain_over_200"]
            partial_true += marked_partial
        if changed:
            path.write_text(json.dumps(data, indent=2) + "\n")
    assert transactions == 657
    print(
        f"2023-10: transactions={transactions} "
        f"cap_gain_true={cap_true} partial_sale_true={partial_true}"
    )


if __name__ == "__main__":
    main()
