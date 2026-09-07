create table  if not exists transactions(
	id  UUID DEFAULT gen_random_uuid() primary key,
	title text NOT NULL,
	description text,
    category text,
	transaction_type text check (transaction_type in ('income','expense')) NOT NULL,
	value numeric(19, 2) NOT NULL CHECK (value >= 0),
    raw_message text NOT NULL,
	created_time TIMESTAMPTZ,
	updated_time TIMESTAMPTZ
);

create table if not exists agents(
    id UUID DEFAULT gen_random_uuid() primary key,
    agent_name VARCHAR (100) NOT NULL,
    description TEXT NOT NULL,
    system_prompt TEXT,
    model VARCHAR(100),
    is_enable BOOLEAN NOT NULL DEFAULT TRUE,
    created_time TIMESTAMPTZ,
    updated_time TIMESTAMPTZ
);

create table if not exists agent_messages(
    id  UUID DEFAULT gen_random_uuid() primary key,
    agent_id UUID REFERENCES agents(id),
    channel_id VARCHAR(32) NOT NULL,
    discord_message_id BIGINT NOT NULL,
    discord_reply_user_message_id BIGINT,
    context text NOT NULL,
    created_time TIMESTAMPTZ,
    updated_time TIMESTAMPTZ
);


