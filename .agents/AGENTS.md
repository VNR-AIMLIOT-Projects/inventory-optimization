# Documentation & Specification Workflow

Every time you finish a feature, fix a bug, or make significant changes to this repository, you **MUST** follow this workflow before completing the task:

1. **Write a Specification/Fix Document**: Create a Markdown file explaining what you changed, why you changed it, and how the new logic or feature works. Include the architectural decisions and testing steps.
2. **Store the Document**: Save this document in the `docs/specs/` directory using a descriptive filename containing the date (e.g., `docs/specs/YYYY-MM-DD-feature-name.md`).
3. **Commit Caution (No Junk Files)**: NEVER blindly run `git add .`. Always run `git status` first to review untracked files. Do not commit temporary scratch files, debug text files (e.g., `body_*.txt`), or local artifacts. Only commit the actual project code and the newly created spec document.
4. **Finalize**: Add the specific files to Git and commit them with a descriptive commit message.

*Note: This rule applies automatically to all agent workflows in this workspace.*
