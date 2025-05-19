// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  final String baseUrl = "http://10.0.2.2:8000";

  Future<Map<String, dynamic>?> login(String username, String password) async {
    final url = Uri.parse("$baseUrl/auth/login");
    try {
      final resp = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      );
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  Future<bool> register(String username, String email, String password) async {
    final url = Uri.parse("$baseUrl/auth/register");
    try {
      final resp = await http.post(url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "username": username,
          "email": email,
          "password": password
        }),
      );
      return (resp.statusCode >= 200 && resp.statusCode < 300);
    } catch (e) {
      return false;
    }
  }

  Future<Map<String, dynamic>> enterQueue(String token, String timeOption) async {
    final url = Uri.parse("$baseUrl/game/queue");
    try {
      final resp = await http.post(url,
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer $token"
        },
        body: jsonEncode({"time_option": timeOption}),
      );
      return jsonDecode(resp.body);
    } catch (e) {
      return {"status": "error", "message": e.toString()};
    }
  }

  Future<Map<String, dynamic>?> confirmMove(String token, String gameId, Map<String, dynamic> moveData) async {
    final url = Uri.parse("$baseUrl/game/move/$gameId");
    try {
      final resp = await http.post(url,
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer $token"
        },
        body: jsonEncode(moveData),
      );
      return jsonDecode(resp.body);
    } catch (e) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> passMove(String token, String gameId) async {
    final url = Uri.parse("$baseUrl/game/move/$gameId");
    try {
      final resp = await http.post(url,
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer $token"
        },
        body: jsonEncode({"pass": true}),
      );
      return jsonDecode(resp.body);
    } catch (e) {
      return null;
    }
  }

  Future<bool> surrender(String token, String gameId) async {
    final url = Uri.parse("$baseUrl/game/surrender/$gameId");
    try {
      final resp = await http.post(url,
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer $token"
        },
      );
      return resp.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  Future<List<dynamic>> fetchActiveGames(String token) async {
    final url = Uri.parse("$baseUrl/game/list/active");
    try {
      final resp = await http.get(url, headers: {
        "Authorization": "Bearer $token"
      });
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  Future<List<dynamic>> fetchFinishedGames(String token) async {
    final url = Uri.parse("$baseUrl/game/list/finished");
    try {
      final resp = await http.get(url, headers: {
        "Authorization": "Bearer $token"
      });
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  Future<Map<String, dynamic>?> fetchUserStats(String token) async {
    final url = Uri.parse("$baseUrl/game/user/stats");
    try {
      final resp = await http.get(url, headers: {
        "Authorization": "Bearer $token"
      });
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  // Ödül kullanma
  Future<Map<String, dynamic>?> useReward(String token, String gameId, String rewardType) async {
    final url = Uri.parse("$baseUrl/reward/use?game_id=$gameId&reward_type=$rewardType");
    try {
      final resp = await http.post(url, headers: {
        "Authorization": "Bearer $token"
      });
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body);
      }
      return null;
    } catch (e) {
      return null;
    }
  }
}
