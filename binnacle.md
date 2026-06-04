""To compare against the new worklflow:

/plan Review the @Handgrip_Calibration/docs/workflow_new.md and identify the style, depth, details and other patterns in regard to the style of the document. Then compare it against the docs @Handgrip_Calibration/docs/workflow.md
@Handgrip_Calibration/docs/applying-calibration-results.md @Handgrip_Calibration/docs/recording.md and all the other files at @Handgrip_Calibration/docs/ . Use the @Handgrip_Calibration/docs/workflow_new.md as authoritative reference and
identify all the redundancies that are produced for the document following the strategy stated at: `/home/levi/Repositories/madhus.project.handgrip.worktrees/docs-mid/.augment/requests/redundancy_refactor.md`; and with that
identification, plan how to consolidate, remove redundancies, reduce the number of documents, in order to keep the @Handgrip_Calibration/docs/workflow_new.md intact, and instead reference that document from the other documents as
required, while also removing the redundant information from the other documents.


"" To update the docs to an improved source code"

 /plan the implementation of @Handgrip_Analysis/ and @LSL_Bridge/ has been updated in coordination, however the documentation updated was deferred to this task. Please review the documentation of both libraries and contrast it againt the
implementation changes as observed in the commit: 927fa489912d2259ba747e8c588e89effa39a536 and detailed in the implementation report:
@`/home/levi/Repositories/madhus.project.handgrip.worktrees/docs-mid/.augment/reports/refactors/s4_lsl_bridge_handgrip_analysis_change_report.md` and identify all the gaps of both libraries documentations versos the current source code
implementation. Finally apply the required updates.


""" To get the improved workflow: "

Please step by step how the Handgrip_Calibration process would be used from init to model implemented on fw (either linear or a new implementation for non-linear or other) . Assume that the LSL_Bridge is alive with both stream streaming the target and reference streams. What would be the first step including commands, configurations, etc? what would happen during that 1' step? what is expected to obtain after the first step? which would be the second step? what would happen during that 2' step? what is expected to obtain after the 2'nd step? which would be the third step? (...) which would be the last step ? What I would get as finall results of the process? How should I use that model? At which step should I implement the model into the FW? The validation is donde with the model implemented on firmware?  If not, how does it work?

Please step by step how the Handgrip_Analysis process would be used from model implemented on fw (either linear or a new implementation for non-linear or other) to computed filter implemented on the LSL_Bridge. Assume that the LSL_Bridge is alive with both stream streaming the target and reference streams, and all the steps documented on the attached workflow for the Handgrip_Calibration was already completed.
Under those assumptions, and considering the current state of the source code of the Handgrip_Analysis lib, What would be the first step including commands, configurations, etc? what would happen during that 1' step? what is expected to obtain after the first step? which would be the second step? what would happen during that 2' step? what is expected to obtain after the 2'nd step? which would be the third step? (...) which would be the last step ? What I would get as finall results of the process? How should I use that model? At which step should I implement the model into the FW? The validation is donde with the model implemented on firmware?  If not, how does it work?


+ finish update to workflow new on calib.
/ validate gap on analysis and bridge
/ Return review the updated workflow.md for analysis.
  - run the workflow update.
- launch how to enable the non-linear models on the calibration.
  - the update the docs to close the gap
-
