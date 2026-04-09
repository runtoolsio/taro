"""
Theme color palette for Rich/Textual styling.

All colors use hex values matching the TARO_THEME Textual theme for a unified look.
Rich resolves hex colors to the nearest terminal color on non-truecolor terminals.
"""

# Palette constants — single source of truth
_PRIMARY = '#3dd6b5'      # electric mint
_SECONDARY = '#9bb1c8'    # cool blue-gray
_ACCENT = '#ffb347'       # apricot amber
_SUCCESS = '#7ee787'      # vivid green
_WARNING = '#ffb347'      # amber warning
_ERROR = '#ff6b6b'        # vivid coral red
_MUTED = '#6f7f96'        # softened slate


def prompt_style():
    """Questionary prompt style matching the Taro palette. Lazy import to avoid top-level dependency."""
    from questionary import Style as QStyle
    return QStyle([
        ('qmark', f'fg:{_PRIMARY} bold'),
        ('question', 'bold'),
        ('pointer', f'fg:{_ACCENT} bold'),
        ('highlighted', f'fg:{_ACCENT} bold'),
        ('answer', f'fg:{_PRIMARY} bold'),
        ('instruction', f'fg:{_MUTED}'),
        ('disabled', f'fg:{_MUTED} italic'),
    ])


class Theme:
    highlight = 'bold'
    job = f'bold {_PRIMARY}'
    instance = _MUTED
    id_separator = ''
    success = _SUCCESS
    error = _ERROR
    warning = _WARNING
    subtle = _MUTED
    idle = _ACCENT
    managed = _PRIMARY
    state_before_execution = _PRIMARY
    state_executing = _PRIMARY
    state_discarded = _WARNING
    state_incomplete = _WARNING
    state_failure = _ERROR
    separator = _MUTED

    # Semantic styles
    title = f'bold {_ACCENT}'
    metadata = _SECONDARY
    label = f'bold {_PRIMARY}'
    section_heading = f'bold {_ACCENT}'

    # Output log styles
    log_timestamp = '#5a6a80'       # dim cool slate — recedes as background reference
    log_logger = '#7a9ec2'          # soft blue — distinct hue from timestamp gray
    log_info = '#4dbda8'            # teal mint — clear identity, ties to brand
    log_debug = '#636b78'           # dim neutral — least prominent level
    log_field_key = '#8a7f91'       # dusty lavender — warm contrast to cool tones
