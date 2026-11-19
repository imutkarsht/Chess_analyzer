"""
Helper utilities for the settings view modules.
"""




def create_icon_button(text, icon_name, callback, parent=None, danger=False, primary=False):
    """Create the central Button with a themed icon."""
    from src.gui.components import Button, ButtonVariant

    variant = (
        ButtonVariant.DANGER
        if danger
        else ButtonVariant.PRIMARY
        if primary
        else ButtonVariant.FILLED
    )
    return Button(text, variant, icon=icon_name, on_click=callback, parent=parent)
