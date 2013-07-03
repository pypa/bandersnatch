import blessings

terminal = blessings.Terminal()


def pytest_terminal_summary(terminalreporter):
    color = terminal.green
    if 'failed' in terminalreporter.stats:
        color = terminal.red
    terminalreporter.write_line(
        color(u'@'*terminalreporter._tw.fullwidth))
