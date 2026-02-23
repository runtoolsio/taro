"""
Standard ANSI color names used as the source of truth for the theme.
Rich/Textual use these names directly; prompt_toolkit requires conversion (see printer._to_pt_style).

BASE 16 COLOURS:
    # Low intensity, dark.
        - black, red, green, yellow, blue, magenta, cyan, gray

    # High intensity, bright.
        - bright_black, bright_red, bright_green, bright_yellow,
          bright_blue, bright_magenta, bright_cyan, white
"""


class Theme:
    highlight = 'bold'
    job = 'bold'
    instance = 'bright_black'
    id_separator = ''
    success = 'green'
    error = 'red'
    warning = 'bright_yellow'
    subtle = 'bright_black'
    idle = 'yellow'
    managed = 'cyan'
    state_before_execution = 'green'
    state_executing = 'blue'
    state_discarded = 'yellow'
    state_incomplete = 'bright_yellow'
    state_failure = 'bright_red'
    separator = 'bright_cyan'
