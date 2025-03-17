namespace Test_api.Models
{
    public class BattleCatsAutoTransferRequest
    {
        public string TransferCode { get; set; }
        public string ConfirmationCode { get; set; }
        public string CountryCode { get; set; } = "en";
        public string GameVersion { get; set; } = "11.3.0";
        public int? CatFood { get; set; }
    }
}
