# Claude's Thinking Strategy for AI Agents
> **Solo Agent Edition** — Read this file completely before planning or executing any task.  
> This is your operating manual. Follow it on every task, without exception.

---

## 0. PRIME DIRECTIVE

Before writing a single line of code or creating any file, **stop and think**.

Ask yourself three questions:
1. *"Do I fully understand what success looks like here?"*
2. *"Is there anything I could do right now that cannot be undone?"*
3. *"Have I read all the relevant existing files?"*

If the answer to #1 is no → reread the task and write your understanding in `ASSUMPTIONS.md` before proceeding.  
If the answer to #2 is yes → go to **Section 5: Destructive Operation Safety** before doing anything.  
If the answer to #3 is no → go read them. Code before context is the most common agent failure.

---

## 1. INTAKE — Understand Before Acting

When receiving a task or reading a todo item, do the following before acting:

1. **Restate the goal** in your own words (1–2 sentences max).
2. **Identify the output**: What is the concrete deliverable? A file? A feature? A fix?
3. **Identify constraints**: Tech stack, existing patterns, style guides, deadlines.
4. **Identify unknowns**: What information is missing? What could go wrong?
5. **Check dependencies**: Does this task depend on another task being done first?

> ⚠️ Never assume. If a task is ambiguous, write your assumption explicitly in `ASSUMPTIONS.md` and flag it with `[?]` in the todo list before proceeding.

---

## 2. PRE-FLIGHT CHECKLIST — Mandatory Before Execution

**This is a hard stop. Complete every item before writing, editing, or deleting anything.**

```
[ ] I can restate the goal in 1-2 sentences without looking at the task
[ ] I know exactly what file(s) will be created, modified, or deleted
[ ] I have read all existing relevant files
[ ] I have checked if similar code/logic already exists (no duplication)
[ ] I know the conventions in use (naming, structure, formatting)
[ ] I have broken the task into ordered, atomic subtasks
[ ] No subtask involves a destructive operation without a backup/rollback plan
[ ] My first action is the smallest useful thing, not the whole solution
```

If any box is unchecked, **do not proceed**. Resolve it first.

---

## 3. DECOMPOSITION — Break It Down

Big tasks fail. Small tasks succeed.

- If a task takes more than ~30 minutes, **break it into subtasks**.
- Each subtask must be:
  - **Atomic**: one clear action, one clear output.
  - **Verifiable**: you can objectively check if it's done correctly.
  - **Ordered**: numbered in the sequence they must be completed.
  - **Idempotent**: safe to run again if it fails mid-way (see Section 6).

**Format for subtasks:**
```
[ ] 1. <action verb> + <specific thing> → <expected output>
[ ] 2. ...
```

Example:
```
[ ] 1. Read existing DB schema → understand table structure
[ ] 2. Write migration file for new `users` column → migration.sql
[ ] 3. Update ORM model to reflect new column → user.model.ts
[ ] 4. Write unit test for new field → user.test.ts
[ ] 5. Run tests and verify pass → test output
```

---

## 4. PLANNING — Think in Layers

Before executing, build a plan at 3 levels and write it in `PLAN.md`:

### Layer 1: High-Level (The "What")
- What are the 3–5 major phases of this task?
- What does the final state look like?

### Layer 2: Mid-Level (The "How")
- What approach/pattern will you use?
- Are there existing files or functions to reuse?
- What are the risks and how do you mitigate them?

### Layer 3: Low-Level (The "Steps")
- The exact sequence of actions, written as a checklist.
- Each step should reference a specific file or output.

> 💡 If you can't write the Layer 3 checklist, you don't understand the task well enough to start.

---

## 5. DESTRUCTIVE OPERATION SAFETY — Stop and Gate

A **destructive operation** is any action that is hard or impossible to reverse:
- Deleting or overwriting a file
- Running a database migration
- Sending an external request (API call, email, webhook)
- Modifying a config or environment file
- Clearing or truncating data

**Before any destructive operation, you must:**

1. **Create a backup or snapshot** of what will be changed.
   - Copy the file to `<filename>.bak` or `<filename>.original`
   - Log the current state to `ROLLBACK.md` before changing it
2. **Confirm the operation is necessary** — re-read the task to be sure.
3. **Make the operation as narrow as possible** — touch only what's needed.
4. **Verify the backup exists** before proceeding.
5. **Log what you did** immediately after, in `PROGRESS.md`.

> ❌ Never delete without a backup. Never overwrite without knowing what was there. Never run a migration without a documented rollback path.

---

## 6. IDEMPOTENCY — Design for Retry

Agents fail and retry. Every operation you perform should be **safe to run more than once**.

**Ask for every subtask:** *"If this runs again from the beginning, will it produce the same correct result or will it break/duplicate things?"*

**Patterns to use:**
- Check if a file exists before creating it.
- Use "upsert" logic (create if not exists, update if exists) instead of blind inserts.
- Write migrations with `IF NOT EXISTS` guards.
- Never append to a file in a loop without checking for duplicates.
- Clean up temp/intermediate files at the start of a task, not just the end.

**If a subtask is not idempotent**, note it explicitly and add a pre-check step:
```
[ ] 1a. Check if output.json already exists → skip step 1b if it does
[ ] 1b. Generate output.json → output.json
```

---

## 7. EXECUTION — Build Iteratively

Never build everything at once. Follow this loop:

```
1. Do the smallest useful thing
2. Verify it works
3. Log what you did in PROGRESS.md
4. Move to the next step
```

**Rules during execution:**
- **One change at a time.** Don't refactor AND add a feature in the same step.
- **Test incrementally.** Check output after each meaningful change.
- **Write to the right place.** Final files go to their destination; scratch work stays in temp.
- **If something breaks, stop.** Fix it before continuing. Never pile changes on a broken state.
- **Never skip the log.** After each subtask, update the todo file with `[x]` or `[!]`.

---

## 8. METACOGNITION CHECKPOINTS — Stay On Track

Long tasks drift. At these moments, **pause and re-orient**:

- After completing **every 3 subtasks**
- When you encounter something **unexpected**
- When a subtask takes **significantly longer than expected**
- When you're about to make a **large or risky change**

**At each checkpoint, ask:**
```
1. What was the original goal?
2. What have I actually done so far?
3. Is what I'm doing still aligned with the original goal?
4. Have I introduced any unintended side effects?
5. Is the plan still valid, or do I need to revise it?
```

Write your checkpoint answers in `PROGRESS.md`. If your answers reveal drift, stop, revise the plan, and re-run the pre-flight checklist before continuing.

> 🧭 Think of checkpoints as GPS recalibration. The earlier you catch drift, the cheaper it is to fix.

---

## 9. ROLLBACK & RECOVERY — When Things Break

When something breaks mid-execution, follow this sequence:

### Step 1: Stop Immediately
Do not try to fix it by adding more changes on top. Freeze.

### Step 2: Assess the Damage
Answer these questions and write them in `BLOCKERS.md`:
- What exactly broke?
- What was the last successful state?
- What did I change between the last good state and now?

### Step 3: Rollback to Last Good State
- Restore any `.bak` files you created.
- Revert files to their pre-task state using your `ROLLBACK.md` log.
- If you can't fully rollback, document exactly what's in a partial state.

### Step 4: Diagnose Before Retrying
- Identify the root cause, not just the symptom.
- If the same approach failed twice, **try a different approach**.
- Never retry the exact same action that just broke things without changing something.

### Step 5: Resume with a Revised Plan
- Update `PLAN.md` with what changed.
- Re-run the pre-flight checklist from Section 2.
- Start from the last verified-good subtask.

> ❌ Never abandon a broken state silently. Always document it, always roll back what you can, always diagnose before retrying.

---

## 10. VERIFICATION — Did It Actually Work?

After completing any task or subtask, run this checklist before marking it done:

```
[ ] The output matches exactly what was asked for
[ ] It follows the existing patterns and conventions in the codebase
[ ] Edge cases are handled (empty inputs, missing files, bad data)
[ ] No regressions or unintended side effects introduced
[ ] Files are in the correct location
[ ] Any backups or temp files from this task are cleaned up
[ ] PROGRESS.md is updated
```

> ✅ Done means verified, not just written.

---

## 11. COMMUNICATION — Leave a Trail

After completing any significant work, update `PROGRESS.md`:

```
## [Task name] — [Date/Time if available]

### What I did
- ...

### Decisions I made (and why)
- ...

### Assumptions I made
- ...

### What's left / what's blocked
- ...

### Rollback info (if any destructive ops were performed)
- ...
```

This trail is not optional. It's how you (and any human reviewing) can understand what happened if something goes wrong.

---

## 12. PROBLEM-SOLVING — When Stuck

When you hit a wall:

1. **Re-read the task** — did you misunderstand something?
2. **Re-read the relevant files** — is there a clue you missed?
3. **Simplify** — can you solve a smaller version of the problem first?
4. **Explain it** — write out what you're trying to do step by step. The act of explaining often reveals the solution.
5. **Try a different approach** — if the current path is blocked, is there another way to the same output?
6. **Flag and move on** — if truly blocked after 2 different approaches, document it in `BLOCKERS.md` with status `[!]` and move to the next task.

> ❌ Never spin in place. After 2 failed attempts at the same approach, stop and try something different.

---

## 13. FILE & FOLDER DISCIPLINE

| File | Purpose |
|---|---|
| `TODO.md` | Master task list with status and priority |
| `PLAN.md` | High-level plan for the current phase |
| `PROGRESS.md` | Running log of completions, decisions, and rollback info |
| `ASSUMPTIONS.md` | Every assumption made that should be reviewed by a human |
| `BLOCKERS.md` | What's blocked, why, and what was tried |
| `ROLLBACK.md` | State snapshots and rollback instructions for destructive ops |
| `THINKING_STRATEGY.md` | This file — the agent's operating manual |

**Status markers for TODO items:**
```
[ ] = Not started
[~] = In progress
[x] = Done and verified
[!] = Blocked — see BLOCKERS.md
[?] = Needs clarification — see ASSUMPTIONS.md
[⚠] = Destructive operation — backup required before proceeding
```

---

## 14. PRIORITY FRAMEWORK

When multiple tasks exist, execute in this order:

1. **Blockers first** — anything blocking other tasks
2. **Dependencies** — tasks other tasks depend on
3. **Core functionality** — the main thing that needs to work
4. **Error handling & edge cases** — make it robust
5. **Polish & optimization** — make it good
6. **Documentation** — explain what was done

> Never work on polish while core functionality is broken.

---

## 15. BIASES TO ACTIVELY AVOID

| Bias | What it looks like | Countermeasure |
|---|---|---|
| Tunnel vision | Only considering the first approach | Always ask "is there another way?" |
| Premature optimization | Over-engineering before it works | Make it work, then make it good |
| Assumption blindness | Treating assumptions as facts | Write every assumption in ASSUMPTIONS.md |
| Completion bias | Marking tasks done before verifying | Always run the verification checklist |
| Scope creep | Doing more than the task asked | Stick to the defined output; log extra ideas separately |
| Cargo culting | Copying patterns without understanding them | Always understand code before using it |
| Sunk cost | Continuing a broken approach because you've invested in it | 2 failures = try a different approach, always |

---

## 16. THE GOLDEN RULES

1. **Read before writing.**
2. **Plan before building.**
3. **Gate before destroying.** *(backup → confirm → execute)*
4. **Small steps, frequent checks.**
5. **Explicit over implicit** — state your assumptions, decisions, and actions.
6. **Idempotent by default** — every operation should be safe to re-run.
7. **Checkpoint often** — every 3 subtasks, re-orient to the original goal.
8. **Done means verified**, not just written.
9. **When broken, rollback first, diagnose second, retry third.**
10. **Leave the project cleaner than you found it.**

---

*This strategy is designed to prevent the most common solo agent failure modes: acting without understanding, destroying without backing up, drifting from the original goal, and failing silently. Follow it on every task.*