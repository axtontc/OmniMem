import pytest
from omnimem.sml_adapter import SMLAdapter, SMLMessage, SMLParseError, SMLIntent, SMLContext, SMLConstraints

import textwrap

def test_sml_adapter_parse_valid():
    yaml_content = textwrap.dedent("""
    a2a_msg: '1.0'
    src: Swarm-Lead
    dst: protocol_specialist
    intent: EXECUTE_TASK
    context:
      task_id: T7
      description: SML Protocol Adapter
    payload: Execute task T7.
    """)
    msg = SMLAdapter.parse(yaml_content)
    assert msg.src == "Swarm-Lead"
    assert msg.intent == SMLIntent.EXECUTE_TASK
    assert getattr(msg.context, "task_id", None) == "T7"
    assert msg.payload == "Execute task T7."

def test_sml_adapter_serialize_valid():
    msg = SMLMessage(
        a2a_msg="1.0",
        src="protocol_specialist",
        dst="Swarm-Lead",
        intent=SMLIntent.RESULT,
        context=SMLContext(files=["/tmp/foo.py"]),
        payload="Task completed."
    )
    yaml_str = SMLAdapter.serialize(msg)
    assert "src: protocol_specialist" in yaml_str
    assert "intent: RESULT" in yaml_str
    assert "task completed" not in yaml_str # Case sensitive check, payload is "Task completed."
    assert "Task completed." in yaml_str
    assert "files:\n  - /tmp/foo.py" in yaml_str

def test_sml_adapter_parse_invalid():
    with pytest.raises(SMLParseError):
        SMLAdapter.parse("not valid yaml: : :")

def test_sml_adapter_missing_required():
    yaml_content = textwrap.dedent("""
    a2a_msg: '1.0'
    src: Swarm-Lead
    """)
    with pytest.raises(SMLParseError):
        SMLAdapter.parse(yaml_content)

def test_sml_adapter_markdown_strip():
    yaml_content = textwrap.dedent("""```yaml
    a2a_msg: '1.0'
    src: Agent1
    dst: Agent2
    intent: INFORM
    payload: Hello
    ```""")
    msg = SMLAdapter.parse(yaml_content)
    assert msg.src == "Agent1"
    assert msg.payload == "Hello"
