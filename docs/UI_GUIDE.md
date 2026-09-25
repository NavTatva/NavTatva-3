# NavTatva interface guide

The redesigned console centres on one workflow: choose an observation, run an analysis, explore its location, and review the evidence. Pipeline timings, system counters, duplicated detection tables, theme controls, and the old five-tab navigation were removed from the main interface.

## Page components

| Component | Purpose | How to use it |
| --- | --- | --- |
| NavTatva logo | Return to a fresh observation workspace. | Click the logo. Existing saved runs remain on disk. |
| Local workspace | Indicates that the local API responded during page loading. | This is a connection indicator, not a guarantee that every scene has every dataset. |
| Observation heading | Identifies the selected location, site and satellite acquisition date. | Dates describe the historical radar image, not today's conditions. |
| Change scene | Switch between the four downloaded radar observations. | Choose a location in the dialog. Previous results and map overlays clear so they cannot be mistaken for the new scene. |
| Settings | Adjust the next analysis without filling the main page with parameters. | Set look-back hours, forecast hours, search radius in kilometres, and the time window on either side of the estimated release. Apply saves the values; closing or pressing Escape discards un-applied edits. |
| Run analysis | Start oil detection, drift modelling and vessel ranking. | The map displays a waiting state with elapsed time. Scene and settings changes are disabled until the request finishes. |
| Observation map | Show the spatial evidence in context. | Drag to pan, use +/− to zoom, and click features for their measurements. Recenter returns to the current observation or analysis extent. |
| Map layers | Reduce the map to the evidence you want to inspect. | Toggle radar imagery, detected slicks, origin/backtrack, forecast, and vessel traffic. The same menu switches between satellite, nautical and graticule backgrounds. |
| Map key, scale and north marker | Help interpret colours, distances and orientation. | Orange indicates oil, red-orange the release zone, and blue the forecast. The scale changes with zoom. |
| Vessel timeline | Replay positions for the ranked vessels. | It appears only when the result contains enough vessel samples. Press Play/Pause or drag the slider; times are UTC. It animates vessel positions, not the evolution of the oil detector. |
| Findings | State the outcome and the minimum useful measurements. | Read the oil area and slick count. A clean-water result says that no slick was identified; a missing-AIS result says attribution is unavailable. Neither means the app failed. |
| Vessel candidates | Present investigation priorities and their supporting evidence. | Search by vessel name or MMSI, expand a vessel for evidence, and use Locate track on map to frame its track. The score is out of 100; it is not a probability of guilt. Simulated traffic is explicitly labelled. |
| Drift & forecast | Explain the estimated release and onward movement. | Expand for release time, uncertainty radius, estimated elapsed time, wind, currents and possible coast impact. Missing currents are stated explicitly. |
| About this observation | Keep provenance and limitations accessible without repeating them throughout the page. | Expand for the satellite, acquisition time, vessel-data type, licensing, and detailed run warnings. |
| Report | Preserve a readable account of the current analysis. | Enabled after a successful run; opens the report in a separate tab. |
| Run data / Map data | Export technical evidence for downstream work. | Inside About this observation, open the job JSON or the GeoJSON map features. These controls are disabled before a run. |
| Field guide | Provide an explanation inside the product. | Open it from the header. It describes the workflow, colours, ranking and limitations. |

## Interpreting the installed demo

- **Caspian Sea:** the verified analysis finds oil and ranks four simulated vessel candidates. Current data is unavailable for this basin, so drift is wind-driven.
- **Arabian Sea:** the provided observation is a clean-water case; attribution is skipped because no slick was detected.
- **Gulf of Mexico / Santa Barbara:** oil detection can run, but recorded US AIS must be ingested before those scenes can provide meaningful vessel attribution. The setup does not fabricate recorded tracks.

The installed detector is a pretrained UNet++ with a timm-efficientnet-b0 encoder. Its checkpoint reports oil IoU 0.889 and pixel accuracy 0.9844 on its validation data. Those are segmentation metrics, not measures of attribution accuracy.

## Layout and verification

The desktop layout pairs a large map with one findings column. On phones, findings follow the map in normal page order. At the narrowest width, Run analysis takes a full row to prevent uneven button wrapping. Technical sections and vessel evidence use native disclosures; settings, scene selection and help use native dialogs with keyboard focus containment and Escape dismissal.

Browser checks covered desktop, compact-laptop and phone layouts, including 1280, 1024, 390 and 320-pixel widths. No horizontal overflow was observed in those checks. A narrow-phone action wrapping issue was fixed. Vessel evidence expansion no longer unexpectedly scrolls the phone back to the map. A live Caspian run completed through the redesigned interface, preserving four ranked candidates; saved-run restoration, missing-AIS messaging, and the clean-water state were also checked. The report endpoint returned HTTP 200.

The full test suite passed with 124 tests. Two tests specific to removed interface panels were retired, and the DOM contract checks were extended to cover cleared containers using replaceChildren. Python analysis code and model weights were not changed by this redesign.

## Upload your own radar observation

**Change scene** now includes **Add a radar observation**. Select a calibrated SAR
GeoTIFF and enter its acquisition time in UTC, then press **Add observation**.
This selects the uploaded scene; **Run analysis** starts detection and, if a slick
is found, automatically fetches recorded AIS for the estimated release area/time.
The map displays download/filtering progress. Repeat analyses reuse the local AIS
cache. Coverage and connection failures are explained in Findings; simulated demo
vessels are never substituted for uploaded observations. Missing wind/current
coverage is also called out. This workflow requires prepared radar imagery, not
arbitrary optical GeoTIFFs.

## Live AIS status

The page footer now shows whether the live recorder needs a key, is connecting,
is recording, or is retrying after a connection problem. Hover for the latest
received-position time. This describes the current connection, not historical
coverage. Uploaded analyses use matching recorded live positions when available;
Findings flags possible reception gaps. Otherwise they try the historical AIS
source. Run `configure-live-ais.command` to supply a key locally.
