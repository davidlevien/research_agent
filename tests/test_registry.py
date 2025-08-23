from research_system.tools.registry import Registry, ToolSpec, Model

class In(Model):  text: str
class Out(Model): echoed: str

def echo_multi(text: str): return [Out(echoed=text), Out(echoed=text.upper())]

def test_registry_list_output():
    r = Registry()
    r.register(ToolSpec(name="echo", fn=echo_multi, input_model=In, output_model=list[Out]))
    out = r.execute("echo", {"text":"hi"})
    assert isinstance(out, list) and out[0].echoed == "hi"