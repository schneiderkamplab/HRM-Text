import 'package:flutter/material.dart';

import 'markdown_text.dart';

class MimirMark extends StatelessWidget {
  final double size;
  const MimirMark({super.key, this.size = 24});
  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(size * .2),
    child: Image.asset(
      'assets/mimir.png',
      width: size,
      height: size,
      semanticLabel: 'DFM Mimir logo',
    ),
  );
}

class ChatMessage extends StatelessWidget {
  final String role, content;
  const ChatMessage({super.key, required this.role, required this.content});
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 26),
    child: Container(
      padding: EdgeInsets.all(role == 'user' ? 16 : 0),
      decoration: BoxDecoration(
        color: role == 'user'
            ? Theme.of(context).colorScheme.primary.withValues(alpha: .07)
            : null,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (role != 'user') ...[
                const MimirMark(size: 20),
                const SizedBox(width: 7),
              ],
              Text(
                role == 'user' ? 'YOU' : 'DFM MIMIR',
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          if (role == 'user')
            SelectableText(
              content,
              style: const TextStyle(fontSize: 15, height: 1.5),
            )
          else
            MarkdownText(content),
        ],
      ),
    ),
  );
}

class ChatWelcome extends StatelessWidget {
  final bool enabled;
  final ValueChanged<String> onPrompt;
  const ChatWelcome({super.key, required this.enabled, required this.onPrompt});
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    child: Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          children: [
            const SizedBox(height: 30),
            const MimirMark(size: 88),
            const SizedBox(height: 20),
            const Text(
              'DFM Mimir',
              style: TextStyle(fontSize: 34, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 15),
            const Text(
              'Ask, explore, or find the right words.\nYour conversation stays on this device.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 22),
            Container(
              color: Colors.white,
              padding: const EdgeInsets.all(12),
              child: Image.asset('assets/dfm.png', width: 170),
            ),
            const SizedBox(height: 24),
            for (final pair in [
              (
                'Forklar noget enkelt',
                'Forklar forskellen mellem vejr og klima kort.',
              ),
              (
                'Help me find the words',
                'Help me write a short, friendly thank-you note.',
              ),
              (
                'Explore an idea',
                'Suggest three creative things to do on a rainy afternoon.',
              ),
            ])
              Padding(
                padding: const EdgeInsets.all(5),
                child: OutlinedButton(
                  onPressed: enabled ? () => onPrompt(pair.$2) : null,
                  child: Text(pair.$1),
                ),
              ),
          ],
        ),
      ),
    ),
  );
}
