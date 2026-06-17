## Project Scout Agent

```text
You are my project scout sub-agent. Read the current FreeGrasp repository
quickly and build an executable map. Do not change code and do not run heavy
evaluation.

Please do the following:
1. List the most important entry-point scripts and what each one does.
2. Mark which scripts may trigger GPU-heavy work, long runtimes, or paid API
   usage.
3. Mark which tests are lightweight and good for everyday regression checks.
4. Give me a recommended reading order for the first 8 files I should open.
5. End with a repository workflow summary in 10 lines or fewer.

Output format:
- Entry points
- Costly or risky commands
- Safe tests
- Recommended reading order
- Workflow summary

Constraints:
- Do not run heavy evaluation
- Do not assume datasets or API keys are available
- Prefer conclusions from local code and docs
- Call out Molmo cache behavior when relevant
```
