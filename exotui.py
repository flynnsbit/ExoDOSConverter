import threading

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, RichLog, Select, Static, Switch

import util
from exoappstate import ExoAppState


class MisterBuildNameScreen(ModalScreen):
    CSS = """
    MisterBuildNameScreen {
        align: center middle;
    }
    #mister_build_dialog {
        width: 72;
        border: heavy $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id='mister_build_dialog'):
            yield Static('Multiple games selected.', classes='section-title')
            yield Label('Enter a collection name for the build folder:')
            yield Input(id='mister_build_name_input')
            with Horizontal(classes='action-row'):
                yield Button('Cancel', id='mister_build_cancel', classes='small-btn')
                yield Button('Use Name', id='mister_build_ok', variant='success', classes='small-btn')

    def on_mount(self):
        self.query_one('#mister_build_name_input', Input).focus()

    def _submit(self):
        buildName = self.query_one('#mister_build_name_input', Input).value.strip()
        self.dismiss(buildName)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == 'mister_build_cancel':
            self.dismiss(None)
            return
        if event.button.id == 'mister_build_ok':
            self._submit()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == 'mister_build_name_input':
            self._submit()


class ExoTUI(App):
    BINDINGS = [
        ('q', 'quit', 'Quit'),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }
    #top {
        height: 1fr;
        layout: horizontal;
    }
    #controls {
        width: 44;
        min-width: 44;
        border: heavy $accent;
        padding: 0 1;
        overflow-y: auto;
    }
    #lists {
        width: 1fr;
        border: heavy $primary;
        padding: 0 1;
        layout: horizontal;
    }
    #available-pane, #selected-pane {
        width: 1fr;
        padding: 0 1;
    }
    #available_games, #selected_games {
        height: 1fr;
        border: round $surface;
    }
    .section-title {
        text-style: bold;
        color: $secondary;
        margin-top: 1;
    }
    .field-label {
        margin-top: 1;
    }
    .action-row {
        height: auto;
        margin-top: 1;
    }
    .small-btn {
        width: 1fr;
        margin-right: 1;
    }
    #status_line {
        color: $success;
        text-style: bold;
    }
    RichLog {
        height: 14;
        border: heavy $boost;
    }
    """

    SWITCH_TO_KEY = {
        'genre_subfolders_switch': 'genreSubFolders',
        'use_keyb2joypad_switch': 'useKeyb2Joypad',
        'map_sticks_switch': 'mapSticks',
        'long_folder_switch': 'longGameFolder',
        'download_on_demand_switch': 'downloadOnDemand',
        'pre_extract_switch': 'preExtractGames',
        'dosbox_pure_zip_switch': 'dosboxPureZip',
        'debug_mode_switch': 'debugMode',
        'expert_mode_switch': 'expertMode',
        'vsync_switch': 'vsyncCfg',
    }

    def __init__(self, scriptDir, logger, title):
        super().__init__()
        self.scriptDir = scriptDir
        self.logger = logger
        self.title = title
        self.state = ExoAppState(scriptDir, logger)
        self.running = False
        self.availableViewCache = []
        self.selectedViewCache = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='top'):
            with Vertical(id='controls'):
                yield Static('Paths', classes='section-title')
                yield Label('Collection folder', classes='field-label')
                yield Input(value=self.state.getValue('collectionDir'), id='collection_dir_input')
                yield Label('Output directory', classes='field-label')
                yield Input(value=self.state.getValue('outputDir'), id='output_dir_input')
                yield Label('Custom selection file', classes='field-label')
                yield Input(value=self.state.getValue('selectionPath'), id='selection_path_input')
                with Horizontal(classes='action-row'):
                    yield Button('Refresh Collection', id='refresh_collection_btn', classes='small-btn')
                    yield Button('Verify', id='verify_btn', classes='small-btn')
                with Horizontal(classes='action-row'):
                    yield Button('Save Config', id='save_conf_btn', classes='small-btn')
                    yield Button('Proceed', id='proceed_btn', variant='success', classes='small-btn')

                yield Static('', id='collection_version_label', classes='field-label')
                yield Static('', id='status_line')

                yield Static('Conversion settings', classes='section-title')
                yield Label('Conversion type', classes='field-label')
                yield Select(
                    [(conversionType, conversionType) for conversionType in util.conversionTypes],
                    value=self.state.getValue('conversionType'),
                    id='conversion_type_select',
                )
                yield Label('Mapper', classes='field-label')
                mapperValues = sorted(
                    list(set(util.mappersDefault + util.mappersBatocera + util.mappersMiSTeR + util.mappersRecalbox))
                )
                mapperValue = self.state.getValue('mapper')
                if mapperValue not in mapperValues:
                    mapperValues = [mapperValue] + mapperValues
                yield Select(
                    [(mapper, mapper) for mapper in mapperValues],
                    value=mapperValue,
                    id='mapper_select',
                )

                yield Label('Use genre subfolders', classes='field-label')
                yield Switch(value=self.state.getBool('genreSubFolders'), id='genre_subfolders_switch')
                yield Label('Use Keyb2Joypad', classes='field-label')
                yield Switch(value=self.state.getBool('useKeyb2Joypad'), id='use_keyb2joypad_switch')
                yield Label('Map analog sticks', classes='field-label')
                yield Switch(value=self.state.getBool('mapSticks'), id='map_sticks_switch')
                yield Label('Long folder names', classes='field-label')
                yield Switch(value=self.state.getBool('longGameFolder'), id='long_folder_switch')
                yield Label('Download on demand', classes='field-label')
                yield Switch(value=self.state.getBool('downloadOnDemand'), id='download_on_demand_switch')
                yield Label('Pre-extract games (legacy)', classes='field-label')
                yield Switch(value=self.state.getBool('preExtractGames'), id='pre_extract_switch')
                yield Label('Rezip for dosbox-pure', classes='field-label')
                yield Switch(value=self.state.getBool('dosboxPureZip'), id='dosbox_pure_zip_switch')
                yield Label('Debug mode', classes='field-label')
                yield Switch(value=self.state.getBool('debugMode'), id='debug_mode_switch')
                yield Label('Expert mode', classes='field-label')
                yield Switch(value=self.state.getBool('expertMode'), id='expert_mode_switch')
                yield Label('Vsync', classes='field-label')
                yield Switch(value=self.state.getBool('vsyncCfg'), id='vsync_switch')

                yield Label('Mount prefix', classes='field-label')
                yield Input(value=self.state.getValue('mountPrefix'), id='mount_prefix_input')
                yield Label('fullResolution', classes='field-label')
                yield Input(value=self.state.getValue('fullresolutionCfg'), id='fullresolution_input')
                yield Label('renderer', classes='field-label')
                yield Input(value=self.state.getValue('rendererCfg'), id='renderer_input')
                yield Label('output', classes='field-label')
                yield Input(value=self.state.getValue('outputCfg'), id='output_cfg_input')

            with Horizontal(id='lists'):
                with Vertical(id='available-pane'):
                    yield Static('Available games', classes='section-title')
                    yield Input(value=self.state.filterValue, placeholder='Filter games...', id='filter_input')
                    yield Static('', id='available_count')
                    yield OptionList(id='available_games')
                    with Horizontal(classes='action-row'):
                        yield Button('Add Highlighted →', id='add_game_btn', classes='small-btn')
                        yield Button('Add Filtered All →', id='add_filtered_btn', classes='small-btn')
                with Vertical(id='selected-pane'):
                    yield Static('Selected games', classes='section-title')
                    yield Static('', id='selected_count')
                    yield OptionList(id='selected_games')
                    with Horizontal(classes='action-row'):
                        yield Button('← Remove Highlighted', id='remove_game_btn', classes='small-btn')
                        yield Button('Clear Selection', id='clear_selection_btn', classes='small-btn')
                    with Horizontal(classes='action-row'):
                        yield Button('Load Selection', id='load_selection_btn', classes='small-btn')
                        yield Button('Save Selection', id='save_selection_btn', classes='small-btn')
        yield RichLog(id='log')
        yield Footer()

    def on_mount(self):
        self.query_one('#collection_version_label', Static).update(
            'Collection version: ' + self.state.getValue('collectionVersion')
        )
        self._refreshGameLists()
        self._applyComponentStateRules()
        self.set_interval(0.1, self._drainLogs)
        self._setStatus('Loading collection...')
        self._disableForRun(True)
        thread = threading.Thread(target=self._refreshCollectionWorker, daemon=True)
        thread.start()

    def _setStatus(self, statusText):
        self.query_one('#status_line', Static).update(statusText)

    def _drainLogs(self):
        logWidget = self.query_one('#log', RichLog)
        while not self.logger.log_queue.empty():
            level, _replaceLine, msg = self.logger.log_queue.get()
            if level == self.logger.ERROR:
                logWidget.write(Text(msg, style='red'))
            elif level == self.logger.WARNING:
                logWidget.write(Text(msg, style='yellow'))
            else:
                logWidget.write(msg)

    def _refreshGameLists(self):
        available = self.state.getAvailableGames()
        selected = self.state.getSelectedGames()
        availableDisplay = [game for game in available if game not in selected]

        availableList = self.query_one('#available_games', OptionList)
        selectedList = self.query_one('#selected_games', OptionList)

        if availableDisplay != self.availableViewCache:
            previousHighlight = availableList.highlighted
            availableList.set_options(availableDisplay)
            if previousHighlight is not None and previousHighlight < len(availableDisplay):
                availableList.highlighted = previousHighlight
            self.availableViewCache = availableDisplay

        if selected != self.selectedViewCache:
            previousHighlight = selectedList.highlighted
            selectedList.set_options(selected)
            if previousHighlight is not None and previousHighlight < len(selected):
                selectedList.highlighted = previousHighlight
            self.selectedViewCache = selected

        self.query_one('#available_count', Static).update(f'Count: {len(availableDisplay)}')
        self.query_one('#selected_count', Static).update(f'Count: {len(selected)}')
        self.query_one('#collection_version_label', Static).update(
            'Collection version: ' + self.state.getValue('collectionVersion')
        )

    def _getHighlightedGame(self, optionListId):
        optionList = self.query_one(optionListId, OptionList)
        highlighted = optionList.highlighted
        if highlighted is None or highlighted < 0:
            return None

        try:
            option = optionList.get_option_at_index(highlighted)
        except Exception:
            return None

        prompt = option.prompt
        if hasattr(prompt, 'plain'):
            return prompt.plain
        if hasattr(prompt, 'markup'):
            return prompt.markup
        if hasattr(prompt, '__str__'):
            return str(prompt)
        return None

    def _disableForRun(self, running):
        self.running = running
        buttonIds = [
            '#refresh_collection_btn',
            '#verify_btn',
            '#save_conf_btn',
            '#proceed_btn',
            '#add_game_btn',
            '#add_filtered_btn',
            '#remove_game_btn',
            '#clear_selection_btn',
            '#load_selection_btn',
            '#save_selection_btn',
        ]
        for buttonId in buttonIds:
            self.query_one(buttonId, Button).disabled = running

    def _applyComponentStateRules(self):
        collectionVersion = self.state.getValue('collectionVersion')
        conversionType = self.state.getValue('conversionType')
        isExoCollection = collectionVersion in [util.EXODOS, util.EXOWIN3X]
        isMister = conversionType == util.mister
        isBatoceraFamily = conversionType in [util.batocera, util.retrobat, util.recalbox]
        expertMode = self.state.getBool('expertMode')

        preExtractSwitch = self.query_one('#pre_extract_switch', Switch)
        dosboxPureZipSwitch = self.query_one('#dosbox_pure_zip_switch', Switch)
        longFolderSwitch = self.query_one('#long_folder_switch', Switch)
        downloadOnDemandSwitch = self.query_one('#download_on_demand_switch', Switch)

        debugModeSwitch = self.query_one('#debug_mode_switch', Switch)
        vsyncSwitch = self.query_one('#vsync_switch', Switch)
        mapperSelect = self.query_one('#mapper_select', Select)
        mapSticksSwitch = self.query_one('#map_sticks_switch', Switch)
        useKeyb2JoypadSwitch = self.query_one('#use_keyb2joypad_switch', Switch)
        expertModeSwitch = self.query_one('#expert_mode_switch', Switch)

        mountPrefixInput = self.query_one('#mount_prefix_input', Input)
        fullresolutionInput = self.query_one('#fullresolution_input', Input)
        rendererInput = self.query_one('#renderer_input', Input)
        outputCfgInput = self.query_one('#output_cfg_input', Input)

        preExtractSwitch.disabled = True
        if preExtractSwitch.value:
            preExtractSwitch.value = False
            self.state.setBool('preExtractGames', False)

        if isExoCollection:
            dosboxPureZipSwitch.disabled = not isBatoceraFamily
            longFolderSwitch.disabled = not isBatoceraFamily
            downloadOnDemandSwitch.disabled = False

            disableDosboxBasic = isMister
            debugModeSwitch.disabled = disableDosboxBasic
            vsyncSwitch.disabled = disableDosboxBasic
            mapperSelect.disabled = disableDosboxBasic
            mapSticksSwitch.disabled = disableDosboxBasic
            useKeyb2JoypadSwitch.disabled = disableDosboxBasic
            expertModeSwitch.disabled = disableDosboxBasic

            disableExpertFields = disableDosboxBasic or not expertMode
            mountPrefixInput.disabled = disableExpertFields
            fullresolutionInput.disabled = disableExpertFields
            rendererInput.disabled = disableExpertFields
            outputCfgInput.disabled = disableExpertFields
        else:
            dosboxPureZipSwitch.disabled = True
            longFolderSwitch.disabled = True
            downloadOnDemandSwitch.disabled = True
            debugModeSwitch.disabled = True
            vsyncSwitch.disabled = True
            mapperSelect.disabled = True
            mapSticksSwitch.disabled = True
            useKeyb2JoypadSwitch.disabled = True
            expertModeSwitch.disabled = True
            mountPrefixInput.disabled = True
            fullresolutionInput.disabled = True
            rendererInput.disabled = True
            outputCfgInput.disabled = True

    def on_input_changed(self, event: Input.Changed):
        inputId = event.input.id
        value = event.value
        if inputId == 'collection_dir_input':
            self.state.setValue('collectionDir', value)
        elif inputId == 'output_dir_input':
            self.state.setValue('outputDir', value)
        elif inputId == 'selection_path_input':
            self.state.setValue('selectionPath', value)
        elif inputId == 'filter_input':
            self.state.setFilter(value)
            self._refreshGameLists()
            return
        elif inputId == 'mount_prefix_input':
            self.state.setValue('mountPrefix', value)
        elif inputId == 'fullresolution_input':
            self.state.setValue('fullresolutionCfg', value)
        elif inputId == 'renderer_input':
            self.state.setValue('rendererCfg', value)
        elif inputId == 'output_cfg_input':
            self.state.setValue('outputCfg', value)

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == 'conversion_type_select' and event.value is not Select.BLANK:
            self.state.setValue('conversionType', event.value)
            self._applyComponentStateRules()
        elif event.select.id == 'mapper_select' and event.value is not Select.BLANK:
            self.state.setValue('mapper', event.value)

    def on_switch_changed(self, event: Switch.Changed):
        switchId = event.switch.id
        if switchId in self.SWITCH_TO_KEY:
            self.state.setBool(self.SWITCH_TO_KEY[switchId], event.value)
            if switchId == 'expert_mode_switch':
                self._applyComponentStateRules()

    def on_button_pressed(self, event: Button.Pressed):
        if self.running:
            return

        buttonId = event.button.id
        if buttonId == 'refresh_collection_btn':
            self._setStatus('Refreshing collection...')
            self._disableForRun(True)
            thread = threading.Thread(target=self._refreshCollectionWorker, daemon=True)
            thread.start()
        elif buttonId == 'verify_btn':
            self.state.verifyPaths()
            self._setStatus('Verify complete')
        elif buttonId == 'save_conf_btn':
            self.state.saveConfFile()
            self._setStatus('Configuration saved')
        elif buttonId == 'proceed_btn':
            self._promptBuildNameIfNeeded()
        elif buttonId == 'add_game_btn':
            gameName = self._getHighlightedGame('#available_games')
            if gameName is not None:
                self.state.selectGames([gameName])
                self._refreshGameLists()
        elif buttonId == 'add_filtered_btn':
            self.state.selectGames(self.state.getAvailableGames())
            self._refreshGameLists()
        elif buttonId == 'remove_game_btn':
            gameName = self._getHighlightedGame('#selected_games')
            if gameName is not None:
                self.state.deselectGames([gameName])
                self._refreshGameLists()
        elif buttonId == 'clear_selection_btn':
            self.state.clearSelection()
            self._refreshGameLists()
        elif buttonId == 'load_selection_btn':
            self.state.loadCustomSelection()
            self._refreshGameLists()
        elif buttonId == 'save_selection_btn':
            self.state.saveCustomSelection()

    def _refreshCollectionWorker(self):
        result = self.state.refreshCollection(buildCache=True)
        self.call_from_thread(self._onRefreshFinished, result)

    def _onRefreshFinished(self, result):
        self._disableForRun(False)
        if result:
            self._setStatus('Collection loaded')
        else:
            self._setStatus('Collection invalid')
        self._refreshGameLists()
        self._applyComponentStateRules()

    def _conversionWorker(self):
        try:
            result = self.state.runConversion()
        except Exception as exception:
            self.logger.log('Unexpected conversion error: %s' % exception, self.logger.ERROR)
            result = False
        self.call_from_thread(self._onConversionFinished, result)

    def _onConversionFinished(self, result):
        self._disableForRun(False)
        self._refreshGameLists()
        if result:
            self._setStatus('Conversion finished')
        else:
            self._setStatus('Conversion failed')

    def _startConversion(self):
        self._setStatus('Conversion running...')
        self._disableForRun(True)
        thread = threading.Thread(target=self._conversionWorker, daemon=True)
        thread.start()

    def _promptBuildNameIfNeeded(self):
        self.state.setBuildOutputName('')
        if len(self.state.getSelectedGames()) > 1:
            self.push_screen(MisterBuildNameScreen(), self._onBuildNamePromptClosed)
            return
        self._startConversion()

    def _onBuildNamePromptClosed(self, buildName):
        if buildName is None:
            self._setStatus('Conversion canceled')
            return

        buildName = buildName.strip()
        if buildName == '':
            self._setStatus('Collection name is required for multi-game builds')
            return

        self.state.setBuildOutputName(buildName)
        self._startConversion()
