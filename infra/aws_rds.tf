resource "aws_db_subnet_group" "watchtower" {
  count = var.enable_aws_resources ? 1 : 0

  name       = "${var.project_name}-db"
  subnet_ids = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-db-subnet"
  }
}

resource "aws_security_group" "rds" {
  count = var.enable_aws_resources ? 1 : 0

  name        = "${var.project_name}-rds"
  description = "PostgreSQL for LangGraph checkpoints"
  vpc_id      = aws_vpc.main[0].id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks[0].id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "watchtower" {
  count = var.enable_aws_resources ? 1 : 0

  identifier             = "${var.project_name}-pg"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.watchtower[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  storage_encrypted      = true

  tags = {
    Name = "${var.project_name}-postgres"
  }
}
