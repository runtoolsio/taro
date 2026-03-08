"""
Theme color palette for Rich/Textual styling.

All colors use hex values matching the TARO_THEME Textual theme for a unified look.
Rich resolves hex colors to the nearest terminal color on non-truecolor terminals.
"""

# Palette constants — single source of truth
_PRIMARY = '#5ec4d4'      # teal
_SECONDARY = '#7b96b0'    # muted steel blue
_ACCENT = '#e0a84c'       # warm amber
_SUCCESS = '#73c974'      # green
_WARNING = '#d49a4e'      # orange
_ERROR = '#e06c75'        # coral red
_MUTED = '#5a6577'        # dim gray-blue


class Theme:
    highlight = 'bold'
    job = 'bold'
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
    title = f'bold {_PRIMARY}'
    metadata = _SECONDARY
    label = 'bold'
    section_heading = 'bold'
