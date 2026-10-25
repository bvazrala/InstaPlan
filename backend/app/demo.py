"""Explicit local-development identity and idempotent synthetic group bootstrap."""
DEMO_USER_ID = "demo-you"
DEMO_TOKEN = "instaplan-local-demo"
DEMO_CHAT_ID = "local-demo-crew"
DEMO_TRIP_ID = "local-demo-trip"


def seed_local_demo(database_engine):
    from sqlmodel import Session, select
    from app.config import get_settings
    from app.models import Chat, ChatMember, Message, User, PublicProfile
    settings = get_settings()
    if not settings.demo_mode or settings.app_env != "dev" or database_engine.dialect.name != "sqlite":
        raise RuntimeError("Local demo bootstrap requires development mode and SQLite")
    people = [(DEMO_USER_ID, "Jordan", "jordan", "AUS", 262),
              ("demo-maya", "Maya", "maya", "BOS", 24),
              ("demo-alex", "Alex", "alex", "LAX", 200),
              ("demo-sam", "Sam", "sam", "DFW", 330)]
    with Session(database_engine) as session:
        for uid, name, handle, airport, hue in people:
            if session.get(User, uid) is None:
                session.add(User(id=uid, display_name=name, handle=handle, home_airport=airport, hue=hue))
            if session.get(PublicProfile,uid) is None:
                session.add(PublicProfile(user_id=uid,avatar_url=f'/planner/people/{handle}.svg'))
        session.commit()
        if session.get(Chat, DEMO_CHAT_ID) is None:
            session.add(Chat(id=DEMO_CHAT_ID, name="Weekend crew (local demo)"))
            session.commit()
            for uid, *_ in people:
                session.add(ChatMember(chat_id=DEMO_CHAT_ID, user_id=uid))
            session.add(Message(chat_id=DEMO_CHAT_ID, sender_id="demo-maya",
                                body="Let’s plan a New York trip! We’re flying from different cities."))
            session.add(Message(chat_id=DEMO_CHAT_ID, sender_id=DEMO_USER_ID,
                                body="I’m in. Let’s compare everyone’s flights and one shared place to stay."))
            session.commit()
