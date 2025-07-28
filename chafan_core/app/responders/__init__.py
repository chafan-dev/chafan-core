from . import question, submission, article, answer

# responders 的设计目的是 models (crud) -> schema (api endpoint)
#   1. responders 不需要鉴权
#   2. responders 可能会访问 crud。例如 responders.question 传入 models.question, 但可能需要 crud read answers
