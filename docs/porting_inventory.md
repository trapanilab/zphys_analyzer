# zPhys Igor-to-Python Port: Initial Inventory

This starter package was generated from the uploaded Igor Pro `.ipf` procedure files.

## Uploaded files

- `JT_zphys_analysis_rtGlobals3_full_v5(1).ipf`: 1259 lines, 16 functions
- `JT_zphys_display_rtGlobals3_full_v5(1).ipf`: 1588 lines, 31 functions
- `JT_zphys_event_analysis_rtGlobals3_full_v5(1).ipf`: 3711 lines, 23 functions
- `JT_zphys_load_rtGlobals3_full_v5(1).ipf`: 2174 lines, 16 functions
- `JT_zphys_panel_rtGlobals3_full_v5(1).ipf`: 1016 lines, 9 functions

## Function inventory


### JT_zphys_analysis_rtGlobals3_full_v5(1).ipf

- `JT_SetDblExpYOffsetToZero()`
- `Avg_2Dwave_BL(tempWaveName)`
- `tempAddWave(numCols)`
- `Hist1(ctrlName)`
- `Hist2(ctrlName)`
- `Hist3(ctrlName,binsize,binnumber,binstart,pointnumber,pointstart)`
- `concat1(ctrlName)`
- `fft_wave1(ctrlName)`
- `average1(ctrlName)`
- `base1(ctrlName)`
- `StitchSweeps(waveListToStitch, destWave)`
- `ZeroSweeps(ctrlName,checked)`
- `concatenateTEMP()`
- `averageTEMP(ctrlName)`
- `cropWaves(ctrlName,tempwavenum1,tempwavenum2)`
- `changeWavepoints(ctrlName)`

### JT_zphys_display_rtGlobals3_full_v5(1).ipf

- `JTz_DisplayWaveExists(waveName)`
- `JTz_DrawEventThreshold(graphName, thresholdValue)`
- `JTz_SetDblExpYOffsetZero()`
- `JTz_AppendSweepToMainPanel(sweepNum)`
- `Plot_Waves(ctrlName, tempwavenum1, tempwavenum2)`
- `Display_Waves_Startle(ctrlName)`
- `Display_Waves(ctrlName)`
- `Display_StimWave(ctrlName)`
- `UserCursorAdjust(graphName)`
- `UserCursorAdjust_ContButtonProc(ctrlName)`
- `UserCursorAdjust_CancelBProc(ctrlName)`
- `Tile_graphs(ctrlName)`
- `Table_Waves(ctrlName)`
- `Waterfall_waves(ctrlName)`
- `Save_Pict(ctrlName)`
- `Save_Binary(ctrlName)`
- `Display_Wanalysis(ctrlName)`
- `Display_HistWaves(ctrlName)`
- `Display_CurrentWave(ctrlName, varNum, varStr, varName)`
- `Display_NextWave(ctrlName)`
- `Display_PrevWave(ctrlName)`
- `Graph_Panel(ctrlName)`
- `Noaxes(ctrlName,checked)`
- `Autoscale(ctrlName, checked)`
- `CloseControl(ctrlName)`
- `updateAmp(ctrlName,value,event)`
- `updatemainAmp(ctrlName,value,event)`
- `updatemain(ctrlName,varNum,varStr,varName)`
- `modifyGraphs(ctrlName)`
- `AddCursorsToGraph(graphName, numCursorsToAdd, traceNameToAddTo, startXval, deltaXval, protocol)`
- `addCategoryToSDP(ctrlName)`

### JT_zphys_event_analysis_rtGlobals3_full_v5(1).ipf

- `Find_Peaks(ctrlName)`
- `Find_Peaks2(ctrlName)`
- `Display_Peaks2(ctrlName)`
- `analyze_ISI(ctrlName)`
- `vector1(ctrlName)`
- `vector2(ctrlName)`
- `vector3(ctrlName)`
- `Spikes_avg2(ctrlName)`
- `Inst_freq2(ctrlName)`
- `Find_StimPeaks(ctrlName)`
- `Tone_Start(ctrlName)`
- `CVwavestats(ctrlName)`
- `avg_ISI(ctrlName)`
- `stimfreqstats(ctrlName)`
- `VectorfromGraphs(ctrlName,ctrlNum)`
- `recurrencePlot(tempstring,tempnum1,tempnum2)`
- `findLatDiff(ctrlName)`
- `colorizeSpiketimes(ctrlName)`
- `find_ALR_amplitude(CtrlName)`
- `findSpikesInSweeps(ctrlName)`
- `intensity_analysis(ctrlName)`
- `adaptation_analysis(ctrlName)`
- `column_analysis(ctrlName)`

### JT_zphys_load_rtGlobals3_full_v5(1).ipf

- `AddWaves2D(ctrlName)`
- `Import_CSV_File(ctrlName)`
- `Import_HEKA_File(ctrlName)`
- `Import_HEKA_Series(ctrlName)`
- `Read_HEKA_Folder(tempFileSelection)`
- `Import_HEKA_Data(currentseries)`
- `Load_HEKA_Wave(ctrlName,ctrlNum)`
- `Select_Series(ctrlName, popNum, popStr)`
- `ReLoad_Sutter_Wave(ctrlName)`
- `Load_Sutter_Wave(ctrlName)`
- `Select_Folder(ctrlName)`
- `Select_Wave(ctrlName)`
- `save1(ctrlName)`
- `Import_ABF_File(ctrlName)`
- `Read_ABF_Header(tempFileSelection)`
- `Import_ABF_Data(tempFileSelection)`

### JT_zphys_panel_rtGlobals3_full_v5(1).ipf

- `JT_settings(ctrlName)`
- `updatePopProtocol(ctrlName,popNum,popStr)`
- `Start_A(loadNum)`
- `SetupMainPanel(loadNum)`
- `adjustRetinaDisp(ctrlName,checked)`
- `MPTabProc(loadName,tab)`
- `UpdateControlPanel(ctrlName, popStr, loadNum)`
- `DataFolderExceptionCheck(Foldername)`
- `Generate_PopList()`

## Recommended porting order

1. Implement the data model and file loaders first.
2. Load `.pxp` into a normalized Python `Recording` object.
3. Recreate the main zPhys control panel with PySide6 and PyQtGraph.
4. Port display/navigation behavior.
5. Port baseline, averaging, concatenation, FFT/area functions.
6. Port event/spike detection and then the higher-level analyses.

## Notes

The Igor code relies heavily on `root:A` globals, named waves, current data folders, and graph callbacks.
The Python version should replace these with explicit state objects and modules.
