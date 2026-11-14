
# XP-AcceptanceAI

### An LLM-Assisted Framework for Selective Acceptance Test Maintenance under Evolving Requirements in Extreme Programming

**Course:** Advanced Software Design and Development Applications (MSCS811)  
**University:** Taibah University  
**Academic Year:** 2026–2027  

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Google Colab](https://img.shields.io/badge/Google-Colab-F9AB00?logo=googlecolab&logoColor=white)
![Testing](https://img.shields.io/badge/Testing-Acceptance-008C77)
![Status](https://img.shields.io/badge/Experiment-Completed-success)

---

## 1. Project Overview

XP-AcceptanceAI is a research project that investigates how Large Language Models (LLMs) can assist in maintaining existing acceptance tests when customer requirements change during Extreme Programming (XP).

Instead of regenerating the entire test suite, the proposed framework identifies affected tests, updates them selectively, and preserves unaffected tests. It also validates the maintained suite against the correct application.

The project uses Gemini 3.5 Flash-Lite, Python, and Google Colab.

## 2. Research Objectives

- Identify acceptance tests affected by changing requirements.
- Update affected tests while preserving unaffected tests.
- Evaluate the ability of maintained tests to detect new and regression faults.
- Compare selective maintenance with direct updating and full test regeneration.
- Investigate the benefits of an additional requirement coverage review.

## 3. Proposed Framework

The framework consists of five main stages:

1. **Impact Identification:** Identify existing test cases that require modification.
2. **Selective Maintenance:** Update affected tests and preserve unaffected tests.
3. **Execution Validation:** Execute the maintained suite against the correct application.
4. **Requirement Coverage Review:** Identify missing positive, negative, and boundary-value tests.
5. **Independent Evaluation:** Measure fault detection using hidden faulty implementations.

### Framework Versions

- **V1 (D):** Impact identification, protected selective maintenance, and execution validation.
- **V2 (D2):** V1 extended with an additive requirement coverage review.

## 4. Experimental Setup

The experiment uses a standalone Python HTTP application inspired by the RealWorld/Conduit API.

The application is an independent prototype, not the upstream RealWorld implementation.

| Experimental component | Value |
|---|---|
| Development pilot | 3 requirement changes |
| Final benchmark | 12 requirement changes |
| Original acceptance tests | 18 per final case |
| Comparison approaches | 6 |
| Repetitions | 3 per case |
| Final evaluation records | 216 |
| Fault variants | 3 per final case |
| Fault opportunities per approach | 108 |
| LLM | Gemini 3.5 Flash-Lite |

The final evaluation includes 144 base evaluations and 72 dependent review records. Reviews are skipped when the parent method fails to produce a valid suite.

## 5. Comparison Approaches

| ID | Approach |
|---|---|
| A | Full test regeneration |
| B | Direct test updating |
| C | Direct updating with validation and repair |
| C2 | C with requirement coverage review |
| D | Selective maintenance (V1) |
| D2 | Selective maintenance with coverage review (V2) |

## 6. Experimental Results

| Method | Valid /36 | New /72 | Regression /36 | Total /108 |
|---|---:|---:|---:|---:|
| A | 35 | 70 | 19 | 89 |
| B | 36 | 72 | 36 | 108 |
| C | 36 | 70 | 36 | 106 |
| C2 | 36 | 72 | 36 | 108 |
| D | 22 | 43 | 22 | 65 |
| D2 | 22 | 44 | 22 | 66 |

### Key Findings

- Direct updating (B) and direct updating with coverage review (C2) detected all 108 fault opportunities.
- The proposed V2 detected all 66 fault opportunities in its 22 valid runs.
- V2 improved upon V1 by detecting an additional boundary-related fault.
- Invalid impact-selection outputs prevented 14 selective evaluations from producing valid suites.
- Selective maintenance did not outperform direct updating in the final benchmark.

The results demonstrate the importance of reliable impact identification, preserving existing tests, and validating test effectiveness independently of successful execution.

## 7. Project Files

### Experimental Notebooks

| File | Purpose |
|---|---|
| XP_AcceptanceAI_Pilot.ipynb | Initial three-case development pilot |
| XP_AcceptanceAI_V2.ipynb | Coverage review development |
| XP_AcceptanceAI_Final.ipynb | Final experimental evaluation |

### Python Modules

| File | Purpose |
|---|---|
| pilot.py | Prototype application and acceptance-test execution |
| coverage_v2.py | Requirement coverage review |
| final_study.py | Final benchmark, comparison methods, and evaluation |

### Experimental Results

- `xp_llm_results.zip` — Development pilot results.
- `xp_llm_results_v2.zip` — V2 pilot results.
- `xp_final_results (22).zip` — Final evaluation results, including CSV data and individual JSON records.

## 8. Running the Project

### Google Colab

1. Open [Google Colab](https://colab.research.google.com/).
2. Upload `XP_AcceptanceAI_Final.ipynb`.
3. Run the setup and benchmark validation cells.
4. Configure your own Gemini API key using the notebook's instructions.
5. Execute the experimental batches.
6. Inspect and export the evaluation results.

The final notebook supports checkpointing to resume interrupted experiments.

**Important:** A valid Gemini API key is required for new LLM evaluations. Do not publish API keys in notebooks or source files.

Archived results can be inspected without repeating the LLM experiments. New executions may produce different outputs.

## 9. Limitations and Future Work

The evaluation uses a small synthetic benchmark, one LLM, and three repetitions. The findings are descriptive and do not establish statistical superiority.

Future improvements include:

- Stage-specific prompts for impact identification.
- Stronger structured-output validation and retry mechanisms.
- More diverse applications and regression faults.
- Evaluation with multiple LLMs.
- Independent human assessment of affected tests.

## 10. References

The project is supported by research on acceptance testing, requirements evolution, LLM-assisted test maintenance, and fault-based evaluation.

The complete IEEE-formatted references are provided in the accompanying research report.

RealWorld API specification:
https://docs.realworld.show/specifications/backend/introduction/

---

**XP-AcceptanceAI**

Research project developed for Advanced Software Design and Development Applications (MSCS811), Taibah University.
