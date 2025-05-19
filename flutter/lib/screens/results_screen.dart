// lib/screens/results_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ResultsScreen extends StatefulWidget {
  final String gameId;
  final String token;
  const ResultsScreen({super.key, required this.gameId, required this.token});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  final ApiService _apiService = ApiService();
  Map<String, dynamic>? gameResult;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchResults();
  }

  Future<void> _fetchResults() async {
    List<dynamic> finishedGames = await _apiService.fetchFinishedGames(widget.token);
    setState(() {
      gameResult = finishedGames.firstWhere((g) => g["game_id"] == widget.gameId, orElse: () => null);
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Oyun Sonuçları")),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : gameResult == null
          ? const Center(child: Text("Sonuç bulunamadı."))
          : Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Oyun ID: ${gameResult!["game_id"]}", style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text("Oyuncu 1: ${gameResult!["player1"]} - Puan: ${gameResult!["scores"]["player1"]}"),
            Text("Oyuncu 2: ${gameResult!["player2"]} - Puan: ${gameResult!["scores"]["player2"]}"),
            const SizedBox(height: 8),
            Text("Kazanan: ${gameResult!["winner"]}", style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text("Mayın/Ödül Etkileri:", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            // Bu kısımda ek notlar vs.
            const Text("Kalan Harf Sayısı: ??", style: TextStyle(fontSize: 16)),
          ],
        ),
      ),
    );
  }
}
