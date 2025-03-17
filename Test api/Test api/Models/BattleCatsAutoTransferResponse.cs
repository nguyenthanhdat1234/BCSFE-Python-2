using Newtonsoft.Json;

namespace Test_api.Models
{
    public class BattleCatsAutoTransferResponse
    {
        public bool Success { get; set; }
        public string Message { get; set; }
        public string OldTransferCode { get; set; }
        public string OldConfirmationCode { get; set; }
        public string NewTransferCode { get; set; }
        public string NewConfirmationCode { get; set; }
        public GameValues OriginalValues { get; set; }
        public GameValues ModifiedValues { get; set; }
        public string InquiryCode { get; set; }
    }
    public class GameValues
    {
        public int CatFood { get; set; }
        public int Xp { get; set; }
        public int RareTickets { get; set; }
        public int PlatinumTickets { get; set; }
    }

    public class FlaskAutoTransferResponse
    {
        public string Status { get; set; }
        public string Message { get; set; }
        public string OldTransferCode { get; set; }
        public string OldConfirmationCode { get; set; }
        [JsonProperty("new_transfer_code")]
        public string NewTransferCode { get; set; }
        [JsonProperty("new_confirmation_code")]
        public string NewConfirmationCode { get; set; }
        [JsonProperty("original_values")]
        public GameValues OriginalValues { get; set; }
        [JsonProperty("modified_values")]
        public GameValues ModifiedValues { get; set; }
        [JsonProperty("inquiry_code")]
        public string InquiryCode { get; set; }
    }
}
