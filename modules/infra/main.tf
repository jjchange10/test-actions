resource "null_resource" "infra" {
  triggers = {
    value = "test-both-infra"
  }
}
