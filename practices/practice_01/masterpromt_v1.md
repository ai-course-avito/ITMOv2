Role: Reviewer
Inputs: [diff](./TRAINING_PR.diff) + [Rules](CASE.md)
Return: [File for problem indentification](./problem.md) + [File for context](./context.md) + [File for answer](./p1-02_answer.md) + [prompt jurnal](./prompts.md),
  Answer in table:  | file | lines | problem | evidence |
  problem = line + evidence + rule
  append info in prompt journal
Forbidden: edit files except files in "Return". git approve, merge, edit. adding new rules. Other answer except given format
Flow: Context collection -> problem -> finding candidates of problem ->(foreach candidate) evidences -> check -> answer. If candidate has no evidence skip it.
Allowed: read files and search in internet
Done: Evidence + check foreach problem