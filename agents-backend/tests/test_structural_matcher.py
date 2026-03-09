import unittest
from utils.structural_matcher import find_best_matches, RichNode

class TestStructuralMatcher(unittest.TestCase):

    def test_perfect_match(self):
        mainline = {
            "className": "com.example.User",
            "simpleName": "User",
            "superclass": "BaseEntity",
            "interfaces": ["IUser"],
            "fields": [{"name": "db", "type": "Database"}],
            "methods": ["login"],
            "outgoingCalls": ["java.util.List.add", "com.example.DB.query"]
        }
        
        target = mainline.copy() # Perfect copy
        
        # Another random file
        other = {
            "className": "com.example.Other",
            "simpleName": "Other",
            "superclass": "Object",
            "outgoingCalls": []
        }
        
        results = find_best_matches(mainline, [target, other])
        final_matches = results["matches"]
        
        self.assertEqual(len(final_matches), 1)
        self.assertEqual(final_matches[0]["data"]["className"], "com.example.User")

    def test_refactoring_split(self):
        """Tests if the matcher detects 1-to-N split (Feature Coverage)."""
        
        # Mainline: Does Auth AND Profile
        mainline = {
            "className": "com.example.User",
            "simpleName": "User",
            "methods": ["login", "logout", "getProfile", "updateProfile"],
            "fields": [{"name": "db", "type": "Database"}, {"name": "email", "type": "EmailService"}],
            "outgoingCalls": ["DB.query", "Email.send"]
        }
        
        # Target A: UserAuth (Handles Login/Logout + DB)
        auth_component = {
            "className": "com.example.UserAuth",
            "simpleName": "UserAuth",
            "methods": ["login", "logout"],
            "fields": [{"name": "db", "type": "Database"}],
            "outgoingCalls": ["DB.query"]
        }
        
        # Target B: UserProfile (Handles Profile + Email)
        profile_component = {
            "className": "com.example.UserProfile",
            "simpleName": "UserProfile",
            "methods": ["getProfile", "updateProfile"],
            "fields": [{"name": "email", "type": "EmailService"}],
            "outgoingCalls": ["Email.send"]
        }
        
        # Target C: Unrelated
        garbage = {
            "className": "com.example.Garbage",
            "simpleName": "Garbage",
            "methods": ["garbage"],
            "fields": [],
            "outgoingCalls": []
        }
        
        result_dict = find_best_matches(mainline, [auth_component, profile_component, garbage])
        final_matches = result_dict["matches"]
        
        print("\nMulti-File Match Results:")
        for r in final_matches:
            print(f"- {r['data']['simpleName']} (Score: {r['score']:.2f})")
            
        # Should return BOTH Auth and Profile
        self.assertEqual(len(final_matches), 2)
        names = {r["data"]["simpleName"] for r in final_matches}
        self.assertTrue("UserAuth" in names)
        self.assertTrue("UserProfile" in names)
        
        # Verify Completeness
        completeness = result_dict["completeness"]
        self.assertEqual(completeness["ratio"], 1.0) # Should cover everything
        self.assertEqual(len(completeness["missing"]), 0)

if __name__ == '__main__':
    unittest.main()
