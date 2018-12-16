resource "aws_sns_topic" "push_notification" {
  name = "PushNotification"
}

data "aws_iam_policy_document" "push_notification" {
  statement {
    actions   = ["SNS:Publish"]
    resources = ["${aws_sns_topic.push_notification.arn}"]

    principals {
      type        = "AWS"
      identifiers = "${var.sns_access_account_ids}"
    }
  }
}

resource "aws_sns_topic_policy" "push_notification" {
  arn    = "${aws_sns_topic.push_notification.arn}"
  policy = "${data.aws_iam_policy_document.push_notification.json}"
}
