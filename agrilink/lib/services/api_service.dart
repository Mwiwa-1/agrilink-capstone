import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  
  static const String baseUrl = 'http://127.0.0.1:8000';

  static Future<Map<String, dynamic>?> login(String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        print('Login failed: ${response.body}');
        return null;
      }
    } catch (e) {
      print('Error connecting to server: $e');
      return null;
    }
  }
}
