SELECT votes.vote_id, creator, question, option, address, privkey, created, ending
FROM votes
LEFT JOIN options on votes.vote_id = options.vote_id
WHERE votes.vote_id = ?