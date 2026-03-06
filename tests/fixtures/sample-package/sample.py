from talon import Module, actions

mod = Module()
mod.setting("sample_setting", type=str, default="hello", desc="A sample setting")

@mod.action_class
class Actions:
    def sample_action():
        """A sample action"""
        pass

    def sample_other_action(text: str) -> str:
        """Another sample action"""
        return text
