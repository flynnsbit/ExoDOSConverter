import os.path
import sys

from exotui import ExoTUI
from tuilogger import TuiLogger


if __name__ == "__main__":
    scriptDir = os.path.abspath(os.path.dirname(sys.argv[0]))
    title = 'eXoConverter 0.9.6-beta (Linux TUI)'
    logger = TuiLogger()
    logger.log(title)
    logger.log('Script path : ' + scriptDir)

    app = ExoTUI(scriptDir, logger, title)
    app.run()
