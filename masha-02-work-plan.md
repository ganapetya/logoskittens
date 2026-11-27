# Masha work plan

Step-by-step work for the design in `masha-01-design.md`. Do the steps in order. Do not start a step until the one before it meets its exit check.

Step 3 is underway. Speak on the Talk page asks the ready buddy to record, and a voiced turn delivers PCM to her. The manual check on Masha has not been run. Do not mark step 3 done until that check passes.

This file does not open work-plan item 9 by itself. Item 9 stays closed until step 6. Items 7, 8, and 10–12 stay unstarted the whole way. Do not edit architecture §2, §6, or §8. Do not activate `buddy-two`. Do not build Savelij or Rob.

## Step 1. Players and the link, with no live turn

Open item 9 in `work-plan.md` and say in `AGENTS.md` that this stage is open. Add `config/players.json` with one enabled row: Masha, role `buddy`, actor `buddy-one`, steerer `bob`, token env `MASHA_ATTACH_TOKEN`. Add the `bot-link` package.

Tests, and no robot required:

- A teacher attach, or a steerer other than `bob`, is refused with `role_not_open`.
- A second buddy while one is attached is refused with `one_player`.
- Host mode off refuses with `host_mode_off`.
- A missing, empty, or short token is refused before the digest compare.
- A register stores that body’s speaking action and stance rows. A dropped socket forgets them.
- Delivery of tokens `curiosity` and `agreement` sends that body’s action basenames and no other body’s names.
- Talk tests do not open a socket.

Nothing on a live turn yet. Nothing committed to `JetSpider/ros2_ws.git`.

Exit: `pytest` covers the cases above, and the page still talks to the hub with no robot connected.

## Step 2. Host mode, attach, and the player list

The Talk page gets the host-mode switch and the player list. Host mode defaults off. On shows the dial URL. Each row shows the display name, role, steerer, registered speaking action, registered stance tokens, and Ready or the first reason.

She can attach on `/players`. The page shows text and does not play audio. `getUserMedia` is not used. No poses yet, so a reply would hold still. This step does not require her speaker.

Exit: with host mode off, a client attach is refused and the page says so. With host mode on, a client that registers shows up on the page with its tokens. A second browser tab does not see that session. Desktop width and a narrow viewport both show the switch and the list.

## Step 3. She hears and speaks, Speak button first

In `ganapetya/masha`, add `ros2_ws/src/lk_body` and commit it from `/home/ubuntu`. `lk_bot_mode enter` stops the `startup_test` launch and starts `lk_body`. `leave` stops `lk_body` and starts that launch again. Bringup stays up.

Listen mode for this step is `speak` only. Hold Speak to record. Release sends one wav. A pause while the button is held stays one utterance. She plays PCM on Pulse and plays `speaking_masha` while the line plays. Author that file on her from `init_pose`, changing only servo 24.

Manual check:

- Host mode on, her mode entered, the page shows Ready.
- Hold Speak, say one English sentence, release. Hear her. See the gripper open and close. Legs stay a stand. The transcript matches what was said.
- The same in Norsk.
- Hold through a short pause. One reply, not two.
- She does not take a stance pose.
- `leave` brings the keyword voice launch back, and bringup was never killed.

Exit: that manual check, plus host tests that a `speak` press and release produce one audio turn.

## Step 4. Stance poses from BOB

BOB’s suggestion gains `poses`, tokens from the set she registered, stored with the steer and attached to the next reply only. `bot-link` maps them to her action names. She runs that list on `/controller/run_actionset` after the jaw roll for that line. Author `lk_agreement`, `lk_disagreement`, `lk_frustration`, and `lk_curiosity` on her, each copied from a stand.

Manual check, still in `speak` mode:

- The first replies do not change her stance.
- After a third reply, the next reply jaws during the line and then moves once, in the order BOB named.
- The replies after that jaw and do not repeat those poses.
- A missing pose file does not move and does not send `stop`.
- She does not publish `/controller/cmd_vel`.

Exit: that manual check, plus a host test that an unknown token is dropped and the steer is kept.

## Step 5. Open listen, two seconds of silence

`open` becomes the default listen mode. She listens without the button. 2000 ms with no voice ends the sentence. She sends that wav and keeps listening. Minimum speech stays 100 ms. The Speak button remains, and choosing it returns to hold-to-talk.

While her speaker is playing, and for 300 ms after it stops, mic sound is not a new sentence. A sentence that arrives during a pose list still cancels the rest of the list with `stop`.

Manual check:

- With the button left alone, say a sentence that pauses for about one second in the middle. One transcript line, one reply.
- Stop speaking and wait two seconds. The reply starts after that gap.
- Her own reply does not show up as the human line.
- Switch to Speak. The mic stays closed until the button is held.
- Switch back to open. She listens again without the button.

Exit: that manual check. Whisper’s own 400 ms gate is unchanged, because the two seconds are applied on her before the wav is sent.

## Step 6. Close the stage

Mark item 9 done in `work-plan.md`. Record the choices in `AGENTS.md`: her mic, her speaker, her servos, `speaking_masha` on servo 24, host Whisper, mimics registered from the robot, `RunActionSet`, domain 27, robots dial `/players`, `bot-link` owns the sockets, `lk_body` lives in `ganapetya/masha`, both sides use `lk_bot_mode`, Speak is the optional mode, open listen uses 2000 ms. Do not write the token value. No behavior change in this step.

Exit: the choices paragraph matches the running system, and items 7, 8, and 10–12 are still unstarted.

## Do not do

- Do not put pulse numbers in git.
- Do not commit `lk_body` to `JetSpider/ros2_ws.git`.
- Do not publish `/controller/cmd_vel` or raw servo pulses from `lk_body`.
- Do not call the standalone action editor controller that opens the servo bus.
- Do not use `asr_node` as the recognizer.
- Do not run the hub, Piper, or Whisper on the Jetson.
- Do not add a screen body, a second buddy, or a teacher prompt in these steps.
