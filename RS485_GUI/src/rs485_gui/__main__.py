"""Entry point for ``python -m rs485_gui``.

Handles ``--help`` / ``-h`` before importing NiceGUI so that the help
message is accessible even when the optional UI dependencies are absent.
"""
import sys

if __name__ == '__main__' or True:
    # Handle --help before importing app (which imports nicegui)
    if '--help' in sys.argv or '-h' in sys.argv:
        from rs485_gui.config.loader import _print_help
        _print_help()
        sys.exit(0)

    from rs485_gui.app import main
    main()
