CREATE TABLE options (
    vote_id TEXT NOT NULL,
    option TEXT NOT NULL,
    address TEXT NOT NULL,
    privkey TEXT NOT NULL,
    PRIMARY KEY (vote_id, option),
    FOREIGN KEY(vote_id) REFERENCES votes(vote_id)
)