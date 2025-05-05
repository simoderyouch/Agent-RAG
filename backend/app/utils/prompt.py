def custom_prompt_template(language):
    return f"""
        You are a concise and factual assistant. Your task is to answer the question strictly based on the context provided.

        - Respond in **{language}** only.
        - Use **HTML article format** (e.g., <code>&lt;article&gt;&lt;p&gt;...&lt;/p&gt;&lt;/article&gt;</code>) if applicable.
        - If HTML is not suitable, return clean plain text.
        - **Only output the final answer** — no reasoning, no steps, no extra commentary.
        - Your answer should be based on **80% provided context** and **20% general knowledge**.
        - End your answer with a percentage indicating how much was based on the provided context.

        Context:
        {{context}}

        Question:
        {{question}}

        Answer:
        """



def custom_summary_prompt_template(language):
    return f"""
        You are a concise summarizer. Your task is to generate a clear and factual summary based on the provided context.

        - Respond in **{language}** only.
        - Format the summary using **HTML article format** (e.g., `<article><p>...</p></article>`) if possible.
        - If HTML is not applicable, return clean plain text.
        - Only output the **final summary** — no steps or analysis.

        Context:
        {{context}}

        Summary:
    """


def custom_question_extraction_prompt_template(language):
    return f"""
        You are an assistant tasked with extracting possible questions from the given context.

        - Respond in **{language}** only.
        - Return the output as a **JSON array of questions** (e.g., `["Question 1?", "Question 2?"]`).
        - Focus only on **important, relevant questions** that someone might ask based on the context.
        - Do not include any explanation or extra text — only the JSON array.

        Context:
        {{context}}

        Questions:
    """