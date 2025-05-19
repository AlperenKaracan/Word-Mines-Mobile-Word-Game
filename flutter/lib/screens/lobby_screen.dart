// lib/screens/lobby_screen.dart
import 'package:flutter/material.dart';
import 'game_screen.dart';
import '../services/api_service.dart';

class LobbyScreen extends StatefulWidget {
  final String token;
  final String username;
  const LobbyScreen({super.key, required this.token, required this.username});

  @override
  State<LobbyScreen> createState() => _LobbyScreenState();
}

class _LobbyScreenState extends State<LobbyScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = false;
  List<dynamic> _activeGames = [];
  List<dynamic> _finishedGames = [];
  double _successRate = 0.0;
  List<dynamic> _pastGames = [];

  final List<Map<String, String>> timeOptions = [
    {"label": "2 Dakika", "value": "2"},
    {"label": "5 Dakika", "value": "5"},
    {"label": "12 Saat", "value": "720"},
    {"label": "24 Saat", "value": "1440"}
  ];

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    await _fetchActiveGames();
    await _fetchFinishedGames();
    await _fetchUserStats();
    await _fetchPastGames();
  }

  Future<void> _fetchActiveGames() async {
    final games = await _apiService.fetchActiveGames(widget.token);
    setState(() => _activeGames = games);
  }

  Future<void> _fetchFinishedGames() async {
    final games = await _apiService.fetchFinishedGames(widget.token);
    setState(() => _finishedGames = games);
  }

  Future<void> _fetchUserStats() async {
    final stats = await _apiService.fetchUserStats(widget.token);
    if (stats != null) {
      setState(() => _successRate = stats["success_rate"] * 1.0);
    }
  }

  Future<void> _fetchPastGames() async {
    final games = await _apiService.fetchFinishedGames(widget.token);
    setState(() => _pastGames = games);
  }

  Future<void> _enterQueue(String timeOption) async {
    setState(() => _isLoading = true);
    final result = await _apiService.enterQueue(widget.token, timeOption);
    setState(() => _isLoading = false);

    if (result["status"] == "matched") {
      final gameId = result["game_id"];
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => GameScreen(gameId: gameId, token: widget.token)),
      );
    } else if (result["status"] == "waiting") {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(result["message"] ?? "Bekliyor...")));
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(result["message"] ?? "Hata")));
    }
  }

  Widget _buildActiveGames() {
    if (_activeGames.isEmpty) {
      return const Center(child: Text("Aktif oyununuz yok."));
    }
    return ListView.builder(
      itemCount: _activeGames.length,
      itemBuilder: (ctx, i) {
        final gm = _activeGames[i];
        return ListTile(
          title: Text("Oyun ID: ${gm["game_id"]}"),
          subtitle: Text("Sıra: ${gm["turn"]}, Skor: P1=${gm["scores"]["player1"]} - P2=${gm["scores"]["player2"]}"),
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) => GameScreen(gameId: gm["game_id"], token: widget.token)),
            );
          },
        );
      },
    );
  }

  Widget _buildFinishedGames() {
    if (_finishedGames.isEmpty) {
      return const Center(child: Text("Biten oyununuz yok."));
    }
    return ListView.builder(
      itemCount: _finishedGames.length,
      itemBuilder: (ctx, i) {
        final gm = _finishedGames[i];
        return ListTile(
          title: Text("Oyun ID: ${gm["game_id"]} | Kazanan: ${gm["winner"] ?? "?"}"),
          subtitle: Text("Skor: P1=${gm["scores"]["player1"]} - P2=${gm["scores"]["player2"]}"),
        );
      },
    );
  }

  Widget _buildProfileDetails() {
    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Kullanıcı: ${widget.username}", style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text("Başarı Oranı: ${_successRate.toStringAsFixed(2)}%", style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 16),
            const Text("Geçmiş Oyunlar:", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            _pastGames.isEmpty
                ? const Text("Geçmiş oyun bulunamadı.")
                : ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _pastGames.length,
              itemBuilder: (ctx, i) {
                final game = _pastGames[i];
                return ListTile(
                  title: Text("Oyun ID: ${game["game_id"]}"),
                  subtitle: Text("Kazanan: ${game["winner"] ?? "Bilinmiyor"}"),
                );
              },
            )
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: Text("Lobi - ${widget.username}"),
          bottom: const TabBar(
            tabs: [
              Tab(text: "Yeni Oyun"),
              Tab(text: "Aktif Oyun"),
              Tab(text: "Biten Oyun"),
              Tab(text: "Profil")
            ],
          ),
        ),
        body: TabBarView(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  ElevatedButton(
                    onPressed: _isLoading ? null : () => _fetchData(),
                    child: const Text("Yenile"),
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: timeOptions.map((opt) {
                      return ElevatedButton(
                        onPressed: _isLoading ? null : () => _enterQueue(opt["value"]!),
                        child: Text(opt["label"]!),
                      );
                    }).toList(),
                  )
                ],
              ),
            ),
            _buildActiveGames(),
            _buildFinishedGames(),
            _buildProfileDetails(),
          ],
        ),
      ),
    );
  }
}
