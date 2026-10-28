# Common Contract Traceability

| Requirement | Implementation | Verification |
|---|---|---|
| FR-001/FR-002 | `app/contract/pages.py`, static page navigation | `tests/contract/test_page_contract.py`, browser smoke |
| FR-003/FR-004/FR-006 | `app/contract/models.py`, `static/js/demo-state.js` | `tests/contract/test_common_contract.py`, `tests/unit/test_demo_state_contract.py` |
| FR-005/FR-010/FR-011 | `app/contract/vocabulary.py`, `app/contract/errors.py` | `tests/contract/test_common_contract.py` |
| FR-007/FR-008/FR-012 | `app/api/models.py`, `app/services/calculator.py` | `tests/contract/test_math_response_contract.py`, `tests/unit/test_math_determinism.py` |
| FR-009 | `static/js/demo-projections.js`, page fallback text | browser smoke and accessibility tests |

The normative definitions are in `data-model.md`, `contracts/page-and-demo.md`, and `contracts/math-api.md`.
