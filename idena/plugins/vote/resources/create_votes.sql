CREATE TABLE votes (
    vote_id TEXT NOT NULL,
    creator TEXT NOT NULL,
	question TEXT NOT NULL,
	created DATETIME DEFAULT CURRENT_TIMESTAMP,
	ending DATETIME,
	PRIMARY KEY (vote_id)
)