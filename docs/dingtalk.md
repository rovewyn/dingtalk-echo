# DingTalk console configuration

## Create an application robot

1. Open the [DingTalk developer console](https://open-dev.dingtalk.com/), sign in, and select the organization where you want to use the robot. You need permission to create and publish an enterprise internal application. Request the organization administrator's developer access if the console denies access.
2. Under application development, create an enterprise internal DingTalk application. Use a name such as Echo Bot and a brief description. Create the application first, then add its robot capability.
3. In the application details, find application capabilities and add Robot. Some console layouts call this Robot and message push. Enable robot configuration and fill in its name, icon, and the required description fields.
4. Set the message receiving mode to Stream. Save or publish the robot configuration. Stream needs outbound Internet access from the bot process; no public HTTP receiving URL, inbound port, domain, or tunnel is required.
5. In application information or credentials, obtain Client ID and Client Secret (also called AppKey and AppSecret). Put them only in your private local .env as described in [setup](setup.md).
6. Complete the console's application release flow. If a version release is required, create a version under version management and release, include the robot capability, set the visible range to include your own organization account, and publish it. Complete administrator approval if required. Saving the robot form alone may not make the application available to you.

Console labels can vary. Follow the application-centered route rather than creating a group custom Webhook robot. This program subscribes only to robot message callbacks through Stream; it does not subscribe to address book events, use interactive cards, or proactively send through the OpenAPI. Enable the robot and the capabilities required by your console; do not add unrelated permissions for this minimal version.

The official [creation tutorial](https://open-dingtalk.github.io/developerpedia/docs/explore/tutorials/stream/bot/go/create-bot/) describes credentials and Stream robot configuration; its console steps are independent of the programming language used by the bot.

## Direct chat acceptance

1. Start the bot from the repository root and wait for its Stream connected message.
2. In the DingTalk client, switch to the same organization and search for the robot's name. If necessary, select the Functions tab in the search results. Open the robot conversation.
3. Send a short text such as Hello. Verify that the robot replies Hello once.
4. Send Chinese text, an emoji, and a multiline message. Verify that the returned content matches. A message delivered as rich text receives the non-text notice rather than a text echo.
5. Send a picture. Verify that the robot replies with its text-only notice.
6. Stop the program. New messages cannot be processed while it is stopped. Restart it and send a new message to verify operation again; do not assume messages sent offline will be replayed.

Record only pass/fail observations for live testing. Do not copy real message payloads, credentials, or session URLs into commits or public reports.

Optional group test: add the application robot under an internal group's settings, robots, and add robot. The group must belong to the application's organization. Select the actual robot from the @ menu and send a text message. Other group messages are not delivered to the robot. See the official [direct and group chat tutorial](https://open-dingtalk.github.io/developerpedia/docs/explore/tutorials/stream/bot/go/test-bot/).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Configuration check exits with code 2 | Both variables exist, are not template values, and are not overridden by empty environment variables. |
| Connection retries repeatedly | App credentials, organization, published robot configuration, Stream mode, outbound HTTPS/WebSocket access, and proxy settings. The log does not reveal private server diagnostics. |
| Robot cannot be found | Same organization, completed application publication, visible range includes your account, and correct robot name/search category. |
| Stream connects but no echo arrives | Send a new message in the robot's own conversation; verify the robot capability is published, no competing process is using the same application, and group messages actually @ the robot. |
| Reply failed | Try a fresh short text. The session webhook may have expired, the reply may have been rate-limited, or network access may have failed. Avoid sending bursts while testing. |

The minimal implementation has no background Windows service or scheduled task. Keep the terminal process running while testing. Always-on hosting can be added separately after direct chat passes.
