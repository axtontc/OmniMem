from omnimem.security_contract import ContractViolationError, MemMCPHookPayload, SchemaValidator, SecurityException


def test_valid_payload():
    data = {"version": "1.0", "event_type": "update", "content": "some valid content", "metadata": {"key": "value"}}
    SchemaValidator.validate_payload(MemMCPHookPayload, data)
    print("Valid payload passed.")


def test_invalid_version():
    data = {"version": "2.0", "event_type": "update", "content": "some valid content", "metadata": {}}
    try:
        SchemaValidator.validate_payload(MemMCPHookPayload, data)
        assert False, "Should have failed on version"
    except ContractViolationError as e:
        print(f"Invalid version caught: {e}")


def test_canary_injection():
    data = {
        "version": "1.0",
        "event_type": "update",
        "content": "CANARY-8B39-4A7F-9C12-E5D67A9B embedded string",
        "metadata": {},
    }
    try:
        SchemaValidator.validate_payload(MemMCPHookPayload, data)
        assert False, "Should have caught canary"
    except SecurityException as e:
        print(f"Canary caught: {e}")


def test_sql_injection():
    data = {"version": "1.0", "event_type": "update", "content": "some content; DROP TABLE users;", "metadata": {}}
    try:
        SchemaValidator.validate_payload(MemMCPHookPayload, data)
        assert False, "Should have caught SQL injection"
    except SecurityException as e:
        print(f"SQL injection caught: {e}")


def test_extra_fields():
    data = {
        "version": "1.0",
        "event_type": "update",
        "content": "valid",
        "metadata": {},
        "malicious_extra": "should be forbidden",
    }
    try:
        SchemaValidator.validate_payload(MemMCPHookPayload, data)
        assert False, "Should have caught extra fields"
    except ContractViolationError as e:
        print(f"Extra fields caught: {e}")


if __name__ == "__main__":
    test_valid_payload()
    test_invalid_version()
    test_canary_injection()
    test_sql_injection()
    test_extra_fields()
    print("All tests passed.")
