\# Project Instructions



\## Source of truth



`PRD.md` is the authoritative product specification for this repository.



Read the entire PRD before implementing or modifying the application. Implement the requirements as written, including acceptance criteria and Definition of Done.



Do not modify `PRD.md` unless explicitly instructed by the user.



\## Working style



The user wants this project completed quickly with minimal back-and-forth.



Do not stop after producing a plan. After inspecting the environment and repository, proceed with implementation.



Do not ask the user to make routine technical decisions. When the PRD leaves a minor implementation detail unspecified, choose the simplest robust solution consistent with:



1\. classification accuracy,

2\. scraping robustness,

3\. ease of use,

4\. maintainability,

5\. Streamlit Community Cloud compatibility.



Only ask the user when work genuinely cannot continue without information that cannot be inferred or safely defaulted.



Do not split the work into artificial micro-tasks requiring user approval after every stage.



Continue through implementation, testing, bug fixing, documentation, and verification until the requested task is complete.



\## Architecture



Keep the application simple and modular.



Do not introduce:



\* databases,

\* authentication,

\* LLM classification,

\* unnecessary service/repository layers,

\* microservices,

\* elaborate design patterns,

\* unnecessary production dependencies.



Follow the project structure proposed in `PRD.md` unless a small adjustment clearly improves the implementation.



\## Python environment



Use a project-local virtual environment if one does not exist.



Install only dependencies needed by the application.



Maintain `requirements.txt`.



The target deployment environment is Streamlit Community Cloud.



\## Quality



Prefer precision over recall for rule-based classification.



Implement conservative keyword rules.



Keep taxonomy, keywords, geography, and portal configuration outside core Python logic as required by PRD.md.



Treat individual source failures as isolated failures. One failed scraper must not crash the entire run.



Do not silently convert parser failures into successful zero-result runs.



\## Scraping



The two direct portal targets are:



\* Inside Lombok — Lombok Tengah category

\* Lombok Post — Lombok Tengah tag



Inspect their current live HTML structure when implementing their parsers instead of guessing selectors.



Use reasonable request timeouts, retry limits, pagination guards, and user-agent headers.



Do not use unnecessarily aggressive crawling.



\## Serper



The application uses a pool of Serper API keys from Streamlit Secrets.



Never hard-code, print, log, expose, copy into documentation, or commit actual API keys.



Do not deliberately exhaust a Serper key to test failover.



Test failover logic primarily using mocks.



During development/live smoke testing, minimize Serper API consumption.



\## Secrets



`.streamlit/secrets.toml` contains local secrets and must never be committed.



A safe `.streamlit/secrets.toml.example` may be created using placeholder values only.



Do not expose secret values in terminal summaries, exception messages, UI, tests, screenshots, or documentation.



\## Testing and verification



Implement the high-value tests required by `PRD.md`.



Run relevant tests after implementing components.



Before declaring completion:



1\. run the full automated test suite;

2\. validate configuration files;

3\. verify the app starts;

4\. perform a minimal representative live smoke test when network access permits;

5\. inspect failures and fix issues rather than only reporting them;

6\. check the implementation against every acceptance criterion and Definition of Done item in `PRD.md`.



Do not add large numbers of low-value tests merely to increase coverage.



\## UI



The application is for a small group of non-technical users.



Keep the one-page Streamlit interface clean, understandable, and practical.



Do not expose technical implementation details in the primary user workflow.



Diagnostics should be useful but compact.



\## Documentation



Maintain a practical `README.md` covering:



\* purpose;

\* local setup;

\* virtual environment;

\* secrets configuration;

\* running Streamlit;

\* configuration CSVs;

\* tests;

\* Streamlit Community Cloud deployment.



\## Completion report



When work is complete, provide a concise report containing:



\* what was implemented;

\* important architecture decisions;

\* tests run and results;

\* live checks performed;

\* any remaining limitation caused by an external website/API;

\* exact command to start the application.



Do not claim something was tested if it was not actually tested.



