Based on the Tool Design Guides, I need you to review this library in order to refactor it. 

# Goal 
Refactor this library into Python standard, using the best coding practices.  

# Tasks 
1. First inventory all the features that you can identify, the overall architecture of the system and your evaluation in regard to the original state of the code. 
2. After that, I need you to plan how to refactor it in order to:
    Achieve the following goals: 
    - use a src-layout structure with it's own pyproject.toml 
    - use hydra for management of configuration,  
    - use proper layered hierarchichal logging (from debug to critical),

  and to: 
    Identify and remove unmaintainable code: 
    - Legacy code, kept for "compatibilty" which is no longer used
    - Dead code/Uneeded features that were left during development
    - Non relevant functionalities that diffuclt maintainability of the code, without adding value in return 
    - Over the top "defensive" code. (evaluate this in regard to the context of the lib) 

# Deliverable
3. Report the refactor plan as a downloadable file in markdown.md  


--------------


Based on the "Tool Design Guides" and modern Python packaging standards, perform a comprehensive technical audit and create a refactor plan for the attached .zip file

# Goal
Standardize the library architecture to improve maintainability, configuration management, and observability using Python best practices.

# Tasks
1. **System Inventory & Evaluation**:
    - Identify and document all existing features.
    - Design an "ideal" architecture for the application, that would optimize for maintainability, configuration management, and observability.
    - Map the current architecture and contrast it with the ideal architecture, and evaluate its technical debt, specifically focusing on the current flat directory structure and other bad practices.

2. **Refactoring Strategy**:
    Plan the transition to a modern stack with the following requirements:
    - **Structural Layout**: Migrate to a `src-layout` (e.g., `LSL_Bridge/src/lsl_bridge/`) to ensure proper package isolation and testing.
    - **Dependency Management**: Define a standard `pyproject.toml` for the sub-module using PEP 621 metadata, using `uv` as the python package manager and  `hatchling` as the build system. 
    - **Configuration**: Standardize on `Hydra` for configuration management. Ensure to not generate conflicts with the usage of other libraries. Avoid hard-coded 'magic' values, and instead define them as constants in the configuration schema.
    - **Observability**: Implement a hierarchical logging system using the standard `logging` library. Replace ad-hoc logging with loggers scoped to modules (e.g., `logging.getLogger(__name__)`) and configurable levels (DEBUG to CRITICAL) via Hydra. Ensure that any logging that goes to the console is also captured in a .log file.
    - **Feature Completeness**: Ensure that ALL the original features that were touched by the refactor, are still present and working as originally intended (unless purposefully removed - se below). Keep full compatibility with the existing CLI and API; and ensure that the application is still functional and compatible with it's original endpoints.

3. **Code Pruning & Debt Identification**:
    Identify and mark for removal:
    - **Legacy Compatibility**: Unused parsers or protocol handlers (e.g., `legacy_pair_lines` mentioned in documentation but potentially obsolete).
    - **Dead Code**: Features or helper functions left over from the initial development of the HX711 or RS485 integration that are no longer referenced.
    - **Bloated Defensive Programming**: Evaluate and simplify "over-defensive" error handling that overlaps with the underlying `pyserial` or `pylsl` robust error management.

# Deliverable
4. Provide the complete refactor plan in a structured Markdown format (`<module_name>_refactor_plan.md`). This document should include the proposed file tree, a mapping of configuration migrations, and a checklist of code sections to be deprecated.


===================

Perfect, I approve the full refactor plan. 

# Task
-  Please proceed with the refactoring as stated in the refactor plan.
-  Organize the implementation of the refactor plan into a logical sequence of tasks. 
-  Start implementing the refactor plan in the order of the tasks, until the entire refactor plan is implemented.

## Validation
- After finishing the full refactoring, validate that the refactor code is still aligned with the refactor plan. Iterate on the refactored code until it is aligned with the plan. Or reach out to me with a reason for the deviation, if the deviation is not trivial or justified. 

## Communication
- If any ambiguity arises -which cannot be resolved by the plan- please reach out to me. 
- When reaching out to me, provide your questions in form of an interactive chat with the options that you are currently evaluating.
  
# Deliverable
1. The full refactored lib as a downloadable compressed file (.zip, .tar.gz, etc.) with the whole implemented code library. 

======================

Perfect, now please finish anything pending on the refactor process, validate against the refactor plan that the refactored library is aligned with the plan,  and return the finished library as a  downloadable compressed file


=======================

Perfect, I approve the Python Refactor Plan. 

# Task 2 & 3: 

## Implement Phase 2 & 3
-  Please proceed with the refactoring as stated in the **Phase 2 & 3** of the refactor plan.
-  Organize the implementation of the refactor plan into a logical sequence of subtasks. 
-  Make sure that the implementation aligns with the `AGENT_PYTHON_GUIDELINES.md`
-  Start implementing the refactor plan in the order of the subtasks, until the entire **Phase 2 & 3** is implemented.

## Validation
- After finishing the full refactoring, validate that the refactor code is still aligned with the refactor plan. 
- Iterate on the refactored code until it is aligned with the plan. Or reach out to me with a reason for the deviation, if the deviation is not trivial or has a valid justification. 

## Communication
- If any ambiguity arises -which cannot be resolved by the plan- please reach out to me. 
- When reaching out to me, provide your questions with the options that you are currently evaluating.
  
# Deliverable
1. The refactored lib with the complete refactoring of **Phase 2 & 3** as a downloadable compressed file with the updated library 



==============================


