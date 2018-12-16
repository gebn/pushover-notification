data "aws_iam_policy_document" "pushover_notification_role_policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_cloudwatch_log_group" "pushover_notification" {
  name              = "/aws/lambda/${aws_lambda_function.pushover_notification.function_name}"
  retention_in_days = 3
}

data "aws_iam_policy_document" "pushover_notification_policy" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.pushover_notification.arn}:*"]
  }
}

resource "aws_iam_policy" "pushover_notification_policy" {
  policy = "${data.aws_iam_policy_document.pushover_notification_policy.json}"
}

resource "aws_iam_role" "pushover_notification_role" {
  // direct attach - no standalone policy
  assume_role_policy = "${data.aws_iam_policy_document.pushover_notification_role_policy.json}"
}

resource "aws_iam_role_policy_attachment" "pushover_notification_policy" {
  role       = "${aws_iam_role.pushover_notification_role.name}"
  policy_arn = "${aws_iam_policy.pushover_notification_policy.arn}"
}

resource "aws_lambda_function" "pushover_notification" {
  filename      = "${var.deployment_package}"
  function_name = "pushover-notification"
  description   = "Sends a push notification via Pushover in response to an SNS message"
  handler       = "pushover_notification.lambda_handler"
  runtime       = "python3.7"
  timeout       = 5
  publish       = "${var.publish_function}"
  role          = "${aws_iam_role.pushover_notification_role.arn}"

  environment {
    variables = {
      DEFAULT_PUSHOVER_APP_TOKEN = "${var.default_pushover_app_token}"
      DEFAULT_PUSHOVER_USER_KEY  = "${var.default_pushover_user_key}"
    }
  }
}

// alias is only updated when publishing the function (tag release)
resource "aws_lambda_alias" "prod" {
  name             = "prod"
  description      = "the latest production release"
  function_name    = "${aws_lambda_function.pushover_notification.arn}"
  function_version = "${aws_lambda_function.pushover_notification.version}"
  count            = "${var.publish_function ? 1 : 0}"
}

// without this, the subscription doesn't work
// https://github.com/hashicorp/terraform/issues/10748#issuecomment-267463350
resource "aws_lambda_permission" "with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.pushover_notification.function_name}"
  principal     = "sns.amazonaws.com"
  source_arn    = "${aws_sns_topic.push_notification.arn}"
}

resource "aws_sns_topic_subscription" "push_notification_lambda" {
  topic_arn = "${aws_sns_topic.push_notification.arn}"
  protocol  = "lambda"
  endpoint  = "${aws_lambda_function.pushover_notification.arn}"
}