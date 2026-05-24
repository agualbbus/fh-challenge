resource "aws_sqs_queue" "dlq" {
  count = var.enable_aws_resources ? 1 : 0

  name                        = "${var.project_name}-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
}

resource "aws_sqs_queue" "work" {
  count = var.enable_aws_resources ? 1 : 0

  name                        = "${var.project_name}.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  visibility_timeout_seconds  = 120
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[0].arn
    maxReceiveCount     = 3
  })
}
