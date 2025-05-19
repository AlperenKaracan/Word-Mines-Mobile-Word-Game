import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'register_screen.dart';
import 'lobby_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final ApiService _apiService = ApiService();

  final _formKey = GlobalKey<FormState>();

  final TextEditingController _urlController = TextEditingController(text: "http://192.168.1.70:8000");
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isLoading = false;

  Future<void> _login() async {
    // 1) Sunucu adresini set et
    _apiService.setBaseUrl(_urlController.text.trim());

    // 2) Form doğrulaması
    if (_formKey.currentState!.validate()) {
      setState(() => _isLoading = true);

      // 3) Giriş isteğini gönder
      final result = await _apiService.login(
        _usernameController.text.trim(),
        _passwordController.text.trim(),
      );

      setState(() => _isLoading = false);

      // 4) Sonuç kontrol
      if (result != null) {
        final token = result["access_token"];
        final uname = result["username"];
        if (!mounted) return;
        // Giriş başarılı, LobbyScreen'e yönlendir
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => LobbyScreen(token: token, username: uname),
          ),
        );
      } else {
        // Giriş başarısız
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Giriş başarısız!")),
        );
      }
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Kelime Mayınları - Giriş")),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: ListView(
            shrinkWrap: true,
            children: [
              TextFormField(
                controller: _urlController,
                decoration: const InputDecoration(
                    labelText: "Sunucu Adresi (ör. http://192.168.1.100:8000)"
                ),
                validator: (val) {
                  if (val == null || val.isEmpty) {
                    return "Sunucu adresi giriniz";
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _usernameController,
                decoration: const InputDecoration(labelText: "Kullanıcı Adı"),
                validator: (val) => val == null || val.isEmpty
                    ? "Kullanıcı adı giriniz" : null,
              ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _passwordController,
                decoration: const InputDecoration(labelText: "Şifre"),
                obscureText: true,
                validator: (val) {
                  if (val == null || val.isEmpty) return "Şifre giriniz";
                  if (val.length < 8) return "En az 8 karakter";
                  return null;
                },
              ),
              const SizedBox(height: 24),

              ElevatedButton(
                onPressed: _isLoading ? null : _login,
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text("Giriş Yap"),
              ),
              const SizedBox(height: 16),

              TextButton(
                onPressed: () {
                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (_) => const RegisterScreen()),
                  );
                },
                child: const Text("Hesabınız yok mu? Kayıt Olun"),
              )
            ],
          ),
        ),
      ),
    );
  }
}
