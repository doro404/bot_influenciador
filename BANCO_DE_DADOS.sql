-- phpMyAdmin SQL Dump
-- version 5.2.0
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Tempo de geração: 31/07/2025 às 00:25
-- Versão do servidor: 10.4.27-MariaDB
-- Versão do PHP: 7.4.33

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `kpftdhra_bot_influenciador`
--

-- --------------------------------------------------------

--
-- Estrutura para tabela `admin_config`
--

CREATE TABLE `admin_config` (
  `id` int(11) NOT NULL,
  `admin_telegram_id` bigint(20) NOT NULL,
  `can_manage_flows` tinyint(1) DEFAULT 1,
  `can_manage_users` tinyint(1) DEFAULT 1,
  `can_view_stats` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Despejando dados para a tabela `admin_config`
--

INSERT INTO `admin_config` (`id`, `admin_telegram_id`, `can_manage_flows`, `can_manage_users`, `can_view_stats`, `created_at`, `updated_at`) VALUES
(1, 6423539592, 1, 1, 1, '2025-07-26 22:24:55', '2025-07-26 22:24:55');

-- --------------------------------------------------------

--
-- Estrutura para tabela `bot_config`
--

CREATE TABLE `bot_config` (
  `id` int(11) NOT NULL,
  `config_key` varchar(100) NOT NULL,
  `config_value` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Despejando dados para a tabela `bot_config`
--

INSERT INTO `bot_config` (`id`, `config_key`, `config_value`, `created_at`, `updated_at`) VALUES
(1, 'admin_telegram_id', '6423539592', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(2, 'bot_token', '7956077534:AAHqjJ0JLJlj04-SQrLZyyekPYP7U0Iltdw', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(3, 'bot_name', 'Bot Influenciador', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(4, 'welcome_message', '👋 Bem-vindo ao Bot Influenciador! Como posso te ajudar?', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(5, 'max_users', '1000', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(6, 'maintenance_mode', 'false', '2025-07-26 22:24:39', '2025-07-26 22:26:02'),
(7, 'collect_phone', 'true', '2025-07-27 02:17:00', '2025-07-27 02:17:00'),
(8, 'collect_email', 'true', '2025-07-27 02:21:17', '2025-07-27 02:21:17'),
(9, 'webhook_enabled', 'true', '2025-07-27 02:29:34', '2025-07-27 02:29:54'),
(10, 'webhook_url', 'https://webhook.site/1e5d89ba-c5c0-4697-b402-d8c17070dec7', '2025-07-27 02:29:34', '2025-07-27 02:30:09'),
(11, 'webhook_events', 'bot_access,cadastro_concluido', '2025-07-27 02:29:34', '2025-07-27 02:29:34'),
(12, 'welcome_media_url', '', '2025-07-30 21:28:11', '2025-07-30 21:45:24'),
(13, 'welcome_media_type', '', '2025-07-30 21:28:11', '2025-07-30 21:45:24'),
(14, 'welcome_enabled', 'false', '2025-07-30 21:28:23', '2025-07-30 21:45:21'),
(15, 'welcome_text', 'teste', '2025-07-30 21:41:25', '2025-07-30 21:41:25');

-- --------------------------------------------------------

--
-- Estrutura para tabela `buttons`
--

CREATE TABLE `buttons` (
  `id` int(11) NOT NULL,
  `step_id` int(11) NOT NULL,
  `button_text` varchar(100) NOT NULL,
  `button_type` enum('url','callback','contact','location') DEFAULT 'callback',
  `button_data` varchar(500) DEFAULT NULL,
  `button_order` int(11) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `flows`
--

CREATE TABLE `flows` (
  `id` int(11) NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `is_default` tinyint(1) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `flow_steps`
--

CREATE TABLE `flow_steps` (
  `id` int(11) NOT NULL,
  `flow_id` int(11) NOT NULL,
  `step_order` int(11) NOT NULL,
  `step_type` enum('text','image','video','video_note','document','audio','button') NOT NULL,
  `content` text DEFAULT NULL,
  `media_url` varchar(500) DEFAULT NULL,
  `button_text` varchar(100) DEFAULT NULL,
  `button_url` varchar(500) DEFAULT NULL,
  `button_callback` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `telegram_id` bigint(20) NOT NULL,
  `username` varchar(100) DEFAULT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `name` varchar(200) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `email` varchar(200) DEFAULT NULL,
  `additional_data` text DEFAULT NULL,
  `webhook_bot_access_sent` tinyint(1) DEFAULT 0,
  `webhook_cadastro_sent` tinyint(1) DEFAULT 0,
  `webhook_sent_at` timestamp NULL DEFAULT NULL,
  `welcome_video_sent` tinyint(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Despejando dados para a tabela `users`
--

INSERT INTO `users` (`id`, `telegram_id`, `username`, `first_name`, `last_name`, `is_active`, `created_at`, `updated_at`, `name`, `phone`, `email`, `additional_data`, `webhook_bot_access_sent`, `webhook_cadastro_sent`, `webhook_sent_at`, `welcome_video_sent`) VALUES
(1, 6423539592, 'saikathesun', 'SAIKA', NULL, 1, '2025-07-26 22:26:12', '2025-07-30 22:24:24', NULL, NULL, NULL, NULL, 1, 1, '2025-07-28 23:24:46', 0),
(2, 123456789, NULL, NULL, NULL, 1, '2025-07-30 21:39:44', '2025-07-30 21:39:44', NULL, NULL, NULL, NULL, 0, 0, NULL, 0);

--
-- Índices para tabelas despejadas
--

--
-- Índices de tabela `admin_config`
--
ALTER TABLE `admin_config`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `admin_telegram_id` (`admin_telegram_id`);

--
-- Índices de tabela `bot_config`
--
ALTER TABLE `bot_config`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `config_key` (`config_key`);

--
-- Índices de tabela `buttons`
--
ALTER TABLE `buttons`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_step_order` (`step_id`,`button_order`);

--
-- Índices de tabela `flows`
--
ALTER TABLE `flows`
  ADD PRIMARY KEY (`id`);

--
-- Índices de tabela `flow_steps`
--
ALTER TABLE `flow_steps`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_flow_order` (`flow_id`,`step_order`);

--
-- Índices de tabela `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `telegram_id` (`telegram_id`);

--
-- AUTO_INCREMENT para tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `admin_config`
--
ALTER TABLE `admin_config`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT de tabela `bot_config`
--
ALTER TABLE `bot_config`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=16;

--
-- AUTO_INCREMENT de tabela `buttons`
--
ALTER TABLE `buttons`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT de tabela `flows`
--
ALTER TABLE `flows`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=38;

--
-- AUTO_INCREMENT de tabela `flow_steps`
--
ALTER TABLE `flow_steps`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=30;

--
-- AUTO_INCREMENT de tabela `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- Restrições para tabelas despejadas
--

--
-- Restrições para tabelas `buttons`
--
ALTER TABLE `buttons`
  ADD CONSTRAINT `buttons_ibfk_1` FOREIGN KEY (`step_id`) REFERENCES `flow_steps` (`id`) ON DELETE CASCADE;

--
-- Restrições para tabelas `flow_steps`
--
ALTER TABLE `flow_steps`
  ADD CONSTRAINT `flow_steps_ibfk_1` FOREIGN KEY (`flow_id`) REFERENCES `flows` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
