output "nat_gateway_id" {
  description = "NAT gateway ID."
  value       = aws_nat_gateway.this.id
}

output "nat_public_ip" {
  description = "Public IP the private subnets use for outbound traffic."
  value       = aws_eip.nat.public_ip
}
