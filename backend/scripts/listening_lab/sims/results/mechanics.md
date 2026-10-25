### vote: 2 yes + 2 no confirms at 50%
- ok: `{"confirmed": true, "poll": {"yes": 2, "no": 2, "needed": 2}}`

### vote: thresholds 40/50/60 → votes needed of 4
- ok: `{"0.4": 2, "0.5": 2, "0.6": 3}`

### vote: changing threshold after votes confirms/unconfirms?
- ok: `{"confirmed_before": false, "after_lowering": false, "yes": 2, "needed": 2}`

### vote: user can flip vote; confirmed plan can't be voted again
- ok: `"rejected: Voting opens once the template is complete and Muse has finished listening"`

### vote: new message while poll open resets votes?
- ok: `{"votes_after_message": {"u1": true}, "note": "fake muse returns flexible again, plan unchanged"}`

### vote: late 'no' cannot block, silent members can't be skipped
- ok: `{"poll_open_with_three_of_four_availabilities": false, "missing": ["when.flexibility · Sam"]}`

### race: destination picked while Muse is mid-call survives
- ok: `{"destination_kept": true}`

### race: starting a new plan while a batch is in flight
- ok: `{"title": "New", "flex": {}, "messages": 0}`

### limits: 2000 vs 2001 chars, whitespace, emoji
- ok: `{"2000": "accepted", "2001": "Message must be 1–2000 characters", "blank": "Message must be 1–2000 characters", "emoji2000": "accepted"}`

### notes: left-truncation at 3000 chars cuts the oldest facts mid-line
- ok: `{"len": 3000, "starts_with": "32\n- fact 33: maya prefers option 33\n- f", "first_fact_kept": false}`

### merge_notes: replace with non-string / append non-list
- ok: `["a", "a\n- ok"]`

### updates: >30 updates silently truncated
- ok: `{"decisions": 30}`

### updates: two updates same field in one batch — last wins (even if an older message)
- ok: `{"meal_type": "dinner"}`

### updates: Muse can write search_area over the initiator's chosen city
- ok: `{"search_area": "Japan", "base_location_kept": "Austin, TX"}`

### updates: hint is accepted even when an exact destination exists; hint never cleared
- ok: `{"destination": {"name": "Cabo Bob's", "place_id": "p", "address": "a", "lat": 0, "lng": 0}, "destination_hint": "Chipotle", "search_area": null, "origins": {}}`

### updates: cluster value types (cuisine str, accommodation 'cabin', meal 'Brunch ')
- ok: `[["accommodation", false, "invalid accommodation"], ["accommodation", true, null], ["trip_type", true, null], ["trip_type", false, "topic field must be a nonempty string"]]`

### updates: when.flexibility accepts any label; nothing normalises or dedups windows
- ok: `{"u1": [{"label": "friday"}, {"label": "Friday"}, {"label": "asdf"}, {"label": "never"}]}`

### budget: bool/NaN/inf/huge/negative/str
- ok: `[["True", false], ["nan", false], ["inf", false], ["1000000000000", false], ["-5", false], ["50", false], ["49.99", true], ["0", true]]`

### http: cross-origin write + oversize body + non-JSON
- ok: `{"cross_origin_text_plain_session": 200, "oversize_8k": "400 b'{\"error\": \"Invalid request size\"}'", "not_json": "400 b'{\"error\": \"Expecting value: line 1 column 1 (char 0)\"}'", "bad_vote": "400 b'{\"error\": \"Voting opens once the template is complete and Muse has finished list'", "origin_any_user": "400 b'{\"error\": \"Unknown simulator user\"}'"}`

