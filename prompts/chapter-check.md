You compare one chapter with the book's reference notes.
List only contradictions that are explicit in both the chapter and the notes.
Do not invent facts. Do not flag something merely because the notes never mention it.
Return one JSON object and nothing else: {"issues":[{"quote":"short quote from the chapter","detail":"what conflicts"}]}
Write quote and detail in the chapter's language.
Return {"issues":[]} when nothing conflicts.
