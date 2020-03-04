data "aws_iam_policy_document" "role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_cloudwatch_log_group" "logs" {
  name              = "/aws/lambda/${aws_lambda_function.pushover_notification.function_name}"
  retention_in_days = 3
}

data "aws_iam_policy_document" "policy" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.logs.arn}:*"]
  }
}

resource "aws_iam_policy" "policy" {
  name_prefix = "pushover-notification-"
  policy      = "${data.aws_iam_policy_document.policy.json}"
}

resource "aws_iam_role" "role" {
  // direct attach - no standalone policy
  name_prefix        = "pushover_notification-"
  assume_role_policy = "${data.aws_iam_policy_document.role_policy.json}"
}

resource "aws_iam_role_policy_attachment" "policy" {
  role       = "${aws_iam_role.role.name}"
  policy_arn = "${aws_iam_policy.policy.arn}"
}

resource "aws_lambda_function" "pushover_notification" {
  filename         = "${var.deployment_package}"
  source_code_hash = "${base64sha256(file(var.deployment_package))}"
  function_name    = "pushover-notification"
  description      = "Sends a push notification via Pushover in response to an SNS message"
  handler          = "pushover_notification.lambda_handler"
  runtime          = "python3.8"
  timeout          = 5
  role             = "${aws_iam_role.role.arn}"

  environment {
    variables = {
      DEFAULT_PUSHOVER_APP_TOKEN = "${var.default_pushover_app_token}"
      DEFAULT_PUSHOVER_USER_KEY  = "${var.default_pushover_user_key}"
    }
  }
}

// without this, the subscription doesn't work
// https://github.com/hashicorp/terraform/issues/10748#issuecomment-267463350
resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.pushover_notification.function_name}"
  principal     = "sns.amazonaws.com"
  source_arn    = "${aws_sns_topic.push_notification.arn}"
}

resource "aws_sns_topic_subscription" "function" {
  topic_arn = "${aws_sns_topic.push_notification.arn}"
  protocol  = "lambda"
  endpoint  = "${aws_lambda_function.pushover_notification.arn}"
}
