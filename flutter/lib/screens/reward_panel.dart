// lib/screens/reward_panel.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class RewardPanel extends StatefulWidget {
  final String token;
  final String gameId;
  final List<String> rewards;
  final VoidCallback onRewardUsed;

  const RewardPanel({
    super.key,
    required this.token,
    required this.gameId,
    required this.rewards,
    required this.onRewardUsed,
  });

  @override
  State<RewardPanel> createState() => _RewardPanelState();
}

class _RewardPanelState extends State<RewardPanel> {
  final ApiService _apiService = ApiService();
  bool _isUsing = false;

  @override
  Widget build(BuildContext context) {
    if (widget.rewards.isEmpty) {
      return const SizedBox.shrink();
    }
    return Container(
      padding: const EdgeInsets.all(8),
      color: Colors.blueGrey.shade100,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text("Ödülleriniz:", style: TextStyle(fontWeight: FontWeight.bold)),
          Wrap(
            spacing: 8,
            children: widget.rewards.map((r) {
              return ElevatedButton(
                onPressed: _isUsing ? null : () async {
                  setState(() => _isUsing = true);
                  final result = await _apiService.useReward(widget.token, widget.gameId, r);
                  setState(() => _isUsing = false);
                  if (result != null && result["message"] != null) {
                    ScaffoldMessenger.of(context)
                        .showSnackBar(SnackBar(content: Text(result["message"].toString())));
                    widget.onRewardUsed();
                  } else {
                    ScaffoldMessenger.of(context)
                        .showSnackBar(const SnackBar(content: Text("Ödül kullanma başarısız.")));
                  }
                },
                child: Text(_rewardLabel(r)),
              );
            }).toList(),
          )
        ],
      ),
    );
  }

  String _rewardLabel(String r) {
    switch(r) {
      case "bolge_yasagi": return "Bölge Yasağı";
      case "harf_yasagi": return "Harf Yasağı";
      case "ekstra_hamle_jokeri": return "Ekstra Hamle Jokeri";
      default: return r;
    }
  }
}
