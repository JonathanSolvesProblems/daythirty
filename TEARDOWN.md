# Teardown, due 2026-10-14

Judging closes 2026-10-08, winners 2026-10-14. On 2026-10-14, remove everything below.
A condition is not a plan; this is the date.

## Account 533354334997 (the working account)

IAM user `unsay-bedrock` started with `IAMFullAccess`, `AmazonBedrockFullAccess`,
`AWSLambda_FullAccess`. Policies attached for this project, to be detached:

- `arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess`
- `arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess`
- `arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess`
- `arn:aws:iam::aws:policy/AmazonS3FullAccess`
- `arn:aws:iam::aws:policy/CloudWatchLogsFullAccess`

Resources the AgentCore starter toolkit created on 2026-09-12 (all `us-east-1`), to
be deleted. `agentcore destroy` from the repo root removes most of them; verify each
one afterwards from the console or CLI rather than trusting the tool's summary:

- AgentCore Runtime `daythirty-SGLNmB3qzW`
  `arn:aws:bedrock-agentcore:us-east-1:533354334997:runtime/daythirty-SGLNmB3qzW`
  This is the one that bills for uptime. Confirm it is gone with
  `aws bedrock-agentcore-control list-agent-runtimes --region us-east-1`.
- ECR repository `bedrock-agentcore-daythirty` (delete with `--force`, it holds images)
- CodeBuild project `bedrock-agentcore-daythirty-builder`
- S3 bucket `bedrock-agentcore-codebuild-sources-533354334997-us-east-1` (empty first)
- IAM role `AmazonBedrockAgentCoreSDKRuntime-us-east-1-e4277ba907`
- IAM role `AmazonBedrockAgentCoreSDKCodeBuild-us-east-1-e4277ba907`
- CloudWatch log group `/aws/bedrock-agentcore/runtimes/daythirty-SGLNmB3qzW-DEFAULT`
- AgentCore Memory `daythirty_mem-UDogCd80Ml`
  `arn:aws:bedrock-agentcore:us-east-1:533354334997:memory/daythirty_mem-UDogCd80Ml`
  The redeploy on 2026-09-12 created it (the first deploy recorded `memory_id: null`).
  Delete it, then confirm with
  `aws bedrock-agentcore-control list-memories --region us-east-1`.

App Runner public demo, created 2026-09-13 (`us-east-1`), bills for the provisioned
instance every hour it exists, so it is the first thing to delete:

- App Runner service `daythirty`
  `arn:aws:apprunner:us-east-1:533354334997:service/daythirty/02ec0a53fc4743ec81e8ec8345043239`
  (https://pstuqwpzp8.us-east-1.awsapprunner.com/). `aws apprunner delete-service --service-arn <arn>`, then confirm with
  `aws apprunner list-services --region us-east-1` and that the URL no longer answers.
- ECR repository `daythirty-web` (delete with `--force`)
- IAM roles `DayThirtyAppRunnerECRAccess` and `DayThirtyAppRunnerInstance`
- Policy `AWSAppRunnerFullAccess` attached to `unsay-bedrock`, to detach
- CloudWatch log groups under `/aws/apprunner/daythirty/`

Then sweep every region for orphans, and delete the user's single access key (created
2026-08-11; `aws iam list-access-keys --user-name unsay-bedrock` shows it) if the account
is no longer in use.

## Account 441138556603 (the credits account)

IAM user `daythirty-hackathon` exists with `AmazonBedrockFullAccess` and `IAMFullAccess`
and zero access keys. Delete the user.

## Sweep script

`scripts/teardown_sweep.py` lists everything above with its current state. Run it before
and after, and do not trust a console status label over a closed port.
